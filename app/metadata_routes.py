"""
Routes for custom metadata management.

Provides endpoints for managing custom field definitions and import mapping templates.
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime
import uuid
import os
import subprocess
import asyncio
import json
from pathlib import Path

from .domain.models import CustomFieldDefinition, ImportMappingTemplate, CustomFieldType
from .services import custom_field_service, import_mapping_service

metadata_bp = Blueprint('metadata', __name__, url_prefix='/metadata')


@metadata_bp.route('/')
@login_required
def index():
    """Metadata management dashboard."""
    try:
        # Get user's custom fields with calculated usage
        user_fields = custom_field_service.get_user_fields_with_calculated_usage_sync(current_user.id)
        if user_fields is None:
            user_fields = []
        # Shareable concept removed; no separate popular fields
        popular_fields = []
        
        # Get user's import templates
        import_templates = import_mapping_service.get_user_templates_sync(current_user.id)
        if import_templates is None:
            import_templates = []
        
        # Check if AI enrichment is available
        from app.admin import load_ai_config
        ai_config = load_ai_config()
        has_perplexity = bool(ai_config.get('PERPLEXITY_API_KEY') or os.getenv('PERPLEXITY_API_KEY'))
        has_openai = bool(ai_config.get('OPENAI_API_KEY'))
        has_ollama = bool(ai_config.get('OLLAMA_BASE_URL'))
        ai_available = has_perplexity or has_openai or has_ollama
        
        return render_template(
            'metadata/index.html',
            user_fields=user_fields,
            popular_fields=popular_fields,
            import_templates=import_templates,
            ai_available=ai_available,
            has_perplexity=has_perplexity
        )
    except Exception as e:
        flash(f'Error loading metadata: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@metadata_bp.route('/fields')
@login_required
def fields():
    """Custom fields management page."""
    try:
        # Get user's custom fields with calculated usage
        user_fields = custom_field_service.get_user_fields_with_calculated_usage_sync(current_user.id)
        if user_fields is None:
            user_fields = []
        # Shareable fields removed
        shareable_fields = []
        
        return render_template(
            'metadata/fields.html',
            user_fields=user_fields,
            shareable_fields=shareable_fields,
            field_types=CustomFieldType
        )
    except Exception as e:
        flash(f'Error loading custom fields: {str(e)}', 'error')
        return redirect(url_for('metadata.index'))


@metadata_bp.route('/fields/create', methods=['GET', 'POST'])
@login_required
def create_field():
    """Create a new custom field definition."""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            display_name = request.form.get('display_name', '').strip()
            field_type = request.form.get('field_type', 'text')
            description = request.form.get('description', '').strip()
            # is_shareable removed (all definitions visible)
            is_shareable = False
            is_global = request.form.get('is_global') == 'on'
            
            current_app.logger.info(f"ℹ️ [METADATA_ROUTES] Received request to create custom field '{name}' for user {current_user.id}")

            # Validation
            if not name or not display_name:
                flash('Name and Display Name are required', 'error')
                return redirect(request.url)
            
            # Check if field name already exists for this user
            existing_fields = custom_field_service.get_user_fields_sync(current_user.id)
            if existing_fields is None:
                existing_fields = []
            if any(field.get('name') == name for field in existing_fields):
                flash('A field with this name already exists', 'error')
                return redirect(request.url)
            
            current_app.logger.info(f"ℹ️ [METADATA_ROUTES] Validation passed for custom field '{name}'. Creating definition.")

            # Create field definition
            field_def = CustomFieldDefinition(
                id=str(uuid.uuid4()),
                name=name,
                display_name=display_name,
                field_type=CustomFieldType(field_type),
                description=description if description else None,
                created_by_user_id=current_user.id,
                is_shareable=is_shareable,
                is_global=is_global
            )
            
            # Handle field type specific configuration
            if field_type in ['rating_5', 'rating_10']:
                rating_max = 5 if field_type == 'rating_5' else 10
                field_def.rating_max = rating_max
                
                # Get custom rating labels if provided
                rating_labels = {}
                for i in range(1, rating_max + 1):
                    label = request.form.get(f'rating_label_{i}', '').strip()
                    if label:
                        rating_labels[i] = label
                field_def.rating_labels = rating_labels
            
            elif field_type in ['list', 'tags']:
                predefined_options = request.form.get('predefined_options', '').strip()
                if predefined_options:
                    field_def.predefined_options = [opt.strip() for opt in predefined_options.split(',') if opt.strip()]
                field_def.allow_custom_options = request.form.get('allow_custom_options') == 'on'
            
            # Set additional properties
            default_value = request.form.get('default_value', '').strip()
            if default_value:
                field_def.default_value = default_value
                
            placeholder_text = request.form.get('placeholder_text', '').strip()
            if placeholder_text:
                field_def.placeholder_text = placeholder_text
                
            help_text = request.form.get('help_text', '').strip()
            if help_text:
                field_def.help_text = help_text
            
            current_app.logger.info(f"ℹ️ [METADATA_ROUTES] Custom field definition for '{name}' created. Saving...")
            
            # Check if custom field service is available (not a stub)
            if hasattr(custom_field_service, '__class__') and 'StubService' in str(custom_field_service.__class__):
                flash('Custom fields functionality is not yet available in this version.', 'warning')
                current_app.logger.warning(f"⚠️ [METADATA_ROUTES] Custom field service is not implemented (stub service)")
                return redirect(url_for('metadata.fields'))
            
            # Save field definition - convert field_def to dict for service call
            field_data = {
                'id': field_def.id,
                'name': field_def.name,
                'display_name': field_def.display_name,
                'field_type': field_def.field_type.value if hasattr(field_def.field_type, 'value') else str(field_def.field_type),
                'description': field_def.description,
                'is_global': field_def.is_global,
                'is_shareable': False,
                'default_value': getattr(field_def, 'default_value', None),
                'placeholder_text': getattr(field_def, 'placeholder_text', None),
                'help_text': getattr(field_def, 'help_text', None),
                'rating_max': getattr(field_def, 'rating_max', None),
                'rating_labels': getattr(field_def, 'rating_labels', {}),
                'predefined_options': getattr(field_def, 'predefined_options', []),
                'allow_custom_options': getattr(field_def, 'allow_custom_options', False)
            }
            
            success = custom_field_service.create_field_sync(current_user.id, field_data)
            
            if success:
                flash(f'Custom field "{display_name}" created successfully!', 'success')
                current_app.logger.info(f"✅ [METADATA_ROUTES] Successfully saved custom field '{name}' for user {current_user.id}")
            else:
                flash('Error creating custom field. Please check logs for details.', 'error')
                current_app.logger.error(f"❌ [METADATA_ROUTES] Failed to save custom field '{name}' for user {current_user.id}")

            return redirect(url_for('metadata.fields'))
            
        except Exception as e:
            current_app.logger.error(f"❌ [METADATA_ROUTES] Unhandled exception in create_field: {e}", exc_info=True)
            flash(f'Error creating custom field: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('metadata/create_field.html', field_types=CustomFieldType)


@metadata_bp.route('/fields/<field_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_field(field_id):
    """Edit an existing custom field definition."""
    try:
        field_def = custom_field_service.get_field_by_id_sync(field_id)
        if not field_def:
            flash('Custom field not found', 'error')
            return redirect(url_for('metadata.index'))
        
        # Check ownership
        if field_def.get('created_by_user_id') != current_user.id:
            flash('You can only edit your own custom fields', 'error')
            return redirect(url_for('metadata.index'))
        
        if request.method == 'POST':
            # Get updated field data
            field_data = {
                'name': request.form.get('name', '').strip(),
                'display_name': request.form.get('display_name', '').strip(),
                'description': request.form.get('description', '').strip(),
                'field_type': request.form.get('field_type', 'text'),
                'is_global': request.form.get('is_global') == 'on'
            }
            
            # Basic validation
            if not field_data['name']:
                flash('Field name is required', 'error')
                return render_template('metadata/edit_field.html', field_def=field_def)
            
            if not field_data['display_name']:
                field_data['display_name'] = field_data['name']
            
            # Update field definition
            updated_field = custom_field_service.update_field_sync(field_id, current_user.id, field_data)
            
            if updated_field:
                flash(f'Custom field "{field_data["display_name"]}" updated successfully!', 'success')
                return redirect(url_for('metadata.index'))
            else:
                flash('Failed to update custom field', 'error')
        
        return render_template('metadata/edit_field.html', field_def=field_def)
        
    except Exception as e:
        flash(f'Error editing custom field: {str(e)}', 'error')
        return redirect(url_for('metadata.index'))


@metadata_bp.route('/fields/<field_id>/delete', methods=['POST'])
@login_required
def delete_field(field_id):
    """Delete a custom field definition."""
    try:
        field_def = custom_field_service.get_field_by_id_sync(field_id)
        if not field_def:
            flash('Custom field not found', 'error')
            return redirect(url_for('metadata.fields'))
        
        # Check ownership
        if field_def.get('created_by_user_id') != current_user.id:
            flash('You can only delete your own custom fields', 'error')
            return redirect(url_for('metadata.fields'))
        
        # Delete field definition
        success = custom_field_service.delete_field_sync(field_id, current_user.id)
        
        if success:
            flash(f'Custom field "{field_def.get("display_name", field_def.get("name"))}" deleted successfully!', 'success')
        else:
            flash('Failed to delete custom field', 'error')
        
    except Exception as e:
        flash(f'Error deleting custom field: {str(e)}', 'error')
    
    return redirect(url_for('metadata.index'))


@metadata_bp.route('/api/fields/search')
@login_required
def search_fields():
    """API endpoint to search custom fields."""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify([])
        
        # Search user's fields and shareable fields
        # TODO: Implement search_fields_sync in KuzuCustomFieldService
        # For now, return empty results
        fields = []
        # fields = custom_field_service.search_fields_sync(query, current_user.id)
        if fields is None:
            fields = []
        
        # Return simplified field data for API
        results = []
        for field in fields[:20]:  # Limit to 20 results
            results.append({
                'id': field.id,
                'name': field.name,
                'display_name': field.display_name,
                'field_type': field.field_type.value,
                'description': field.description,
                'is_shareable': field.is_shareable,
                'is_global': field.is_global,
                'created_by_me': field.created_by_user_id == current_user.id
            })
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metadata_bp.route('/templates')
@login_required
def templates():
    """Import mapping templates management page."""
    try:
        # Get user's templates
        user_templates = import_mapping_service.get_user_templates_sync(current_user.id)
        if user_templates is None:
            user_templates = []
        
        return render_template(
            'metadata/templates.html',
            user_templates=user_templates
        )
    except Exception as e:
        flash(f'Error loading import templates: {str(e)}', 'error')
        return redirect(url_for('metadata.index'))


@metadata_bp.route('/enrichment/start', methods=['POST'])
@login_required
def start_enrichment():
    """Start AI enrichment process"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        limit = int(request.form.get('limit', 5))  # Default to 5 for testing
        no_cover_only = request.form.get('no_cover_only', 'false').lower() == 'true'
        force = request.form.get('force', 'false').lower() == 'true'
        
        # If force is enabled, disable no_cover_only filter
        if force:
            no_cover_only = False
        
        # Check if enrichment is already running
        enrichment_status_file = Path('data/enrichment_status.json')
        if enrichment_status_file.exists():
            with open(enrichment_status_file, 'r') as f:
                status = json.load(f)
                if status.get('running', False):
                    return jsonify({
                        'error': 'Enrichment already running',
                        'status': status
                    }), 400
        
        # Start enrichment in background thread (same process to share KuzuDB connection)
        import threading
        import asyncio
        import argparse
        from scripts.enrich_books import EnrichmentCommand
        
        def run_enrichment():
            try:
                # Update status
                status = {
                    'running': True,
                    'started_at': datetime.now().isoformat(),
                    'limit': limit,
                    'no_cover_only': no_cover_only,
                    'force': force,
                    'processed': 0,
                    'enriched': 0,
                    'failed': 0,
                    'enriched_books': [],  # Track which books were enriched
                    'skipped_books': []   # Track which books were skipped (already enriched)
                }
                with open(enrichment_status_file, 'w') as f:
                    json.dump(status, f)
                
                # Create args namespace for EnrichmentCommand
                args = argparse.Namespace(
                    limit=limit,
                    force=force,
                    dry_run=False,
                    quality_min=0.3,
                    yes=True,
                    book_id=None,
                    book_title=None,
                    no_cover_only=no_cover_only
                )
                
                # Run enrichment directly in same process (shares KuzuDB connection)
                command = EnrichmentCommand(args)
                
                # Run async command in event loop
                asyncio.run(command.run())
                
                # Load final status from script output
                if enrichment_status_file.exists():
                    with open(enrichment_status_file, 'r') as f:
                        status = json.load(f)
                
                # Update status
                status['running'] = False
                status['completed_at'] = datetime.now().isoformat()
                
                with open(enrichment_status_file, 'w') as f:
                    json.dump(status, f)
                    
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                status = {
                    'running': False,
                    'error': str(e),
                    'error_trace': error_trace[-2000:] if len(error_trace) > 2000 else error_trace,
                    'completed_at': datetime.now().isoformat()
                }
                with open(enrichment_status_file, 'w') as f:
                    json.dump(status, f)
        
        thread = threading.Thread(target=run_enrichment, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Enrichment started',
            'limit': limit,
            'no_cover_only': no_cover_only
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@metadata_bp.route('/enrichment/status', methods=['GET'])
@login_required
def enrichment_status():
    """Get enrichment status"""
    try:
        enrichment_status_file = Path('data/enrichment_status.json')
        if enrichment_status_file.exists():
            with open(enrichment_status_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({'running': False})
    except Exception as e:
        return jsonify({'error': str(e), 'running': False}), 500


@metadata_bp.route('/enrichment/enrich_from_url', methods=['POST'])
@login_required
def enrich_from_url_endpoint():
    """Extract book metadata from a specific URL (e.g., ozone.bg, ciela.com)"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        title = data.get('title', '').strip()
        author = data.get('author', '').strip()
        
        # Initialize Perplexity enricher
        from app.services.metadata_providers.perplexity import PerplexityEnricher
        import os
        from app.services.kuzu_async_helper import run_async
        
        api_key = os.getenv('PERPLEXITY_API_KEY')
        if not api_key:
            return jsonify({'error': 'Perplexity API key not configured'}), 500
        
        enricher = PerplexityEnricher(api_key=api_key)
        
        # Extract metadata from URL
        metadata = run_async(enricher.enrich_book_from_url(
            url=url,
            title=title if title else None,
            author=author if author else None
        ))
        
        if not metadata:
            return jsonify({
                'success': False,
                'error': 'Could not extract metadata from URL'
            }), 404
        
        return jsonify({
            'success': True,
            'metadata': metadata,
            'url': url
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error extracting metadata from URL: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@metadata_bp.route('/enrichment/enrich_book', methods=['POST'])
@login_required
def enrich_single_book_endpoint():
    """Enrich a single book using AI"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        book_id = data.get('book_id')
        
        if not book_id:
            return jsonify({'error': 'book_id is required'}), 400
        
        # Get book data from database - use relationship service to check user ownership
        from app.services.kuzu_relationship_service import KuzuRelationshipService
        relationship_service = KuzuRelationshipService()
        
        # Get book by UID with user overlay to verify ownership
        book = relationship_service.get_book_by_uid_sync(book_id, str(current_user.id))
        
        # If book exists but user doesn't own it, add it to user's library
        if not book:
            from app.services.kuzu_book_service import KuzuBookService
            temp_book_service = KuzuBookService(user_id=str(current_user.id))
            book_without_overlay = temp_book_service.get_book_by_id_sync(book_id)
            
            if book_without_overlay:
                # Book exists but not in user's library - add it
                current_app.logger.info(f"Book {book_id} exists but not in user {current_user.id} library, adding it")
                from app.infrastructure.kuzu_repositories import KuzuUserBookRepository
                from app.services.kuzu_async_helper import run_async
                user_book_repo = KuzuUserBookRepository()
                added = run_async(user_book_repo.add_book_to_library(
                    user_id=str(current_user.id),
                    book_id=book_id,
                    reading_status='',
                    ownership_status='owned',
                    media_type=getattr(book_without_overlay, 'media_type', None) or 'physical'
                ))
                if added:
                    # Retry getting the book with user overlay
                    book = relationship_service.get_book_by_uid_sync(book_id, str(current_user.id))
        
        if not book:
            return jsonify({'error': 'Book not found'}), 404
        
        # Also get book service for updates
        from app.services.kuzu_book_service import KuzuBookService
        book_service = KuzuBookService(user_id=str(current_user.id))
        
        # Convert book to dict format
        # Handle both Book domain object and dict formats
        if isinstance(book, dict):
            book_data = {
                'id': book.get('id') or book.get('uid') or book_id,
                'uid': book.get('uid') or book.get('id') or book_id,
                'title': book.get('title', ''),
                'author': book.get('author', ''),
                'cover_url': book.get('cover_url'),
                'description': book.get('description'),
                'language': book.get('language', ''),
            }
        else:
            book_data = {
                'id': str(book.id) if hasattr(book, 'id') else str(book.uid) if hasattr(book, 'uid') else book_id,
                'uid': str(book.uid) if hasattr(book, 'uid') else str(book.id) if hasattr(book, 'id') else book_id,
                'title': book.title if hasattr(book, 'title') else '',
                'author': book.author if hasattr(book, 'author') else '',
                'cover_url': book.cover_url if hasattr(book, 'cover_url') else None,
                'description': book.description if hasattr(book, 'description') else None,
                'language': book.language if hasattr(book, 'language') else '',
            }
        
        # Run enrichment asynchronously
        from app.services.enrichment_service import EnrichmentService
        from app.services.kuzu_async_helper import run_async
        
        enrichment_service = EnrichmentService()
        
        # Enrich book (force=True to always enrich, require_cover=True to prioritize cover)
        coro = enrichment_service.enrich_single_book(
            book_data=book_data,
            force=True,
            require_cover=True
        )
        metadata = run_async(coro)
        
        if not metadata:
            return jsonify({
                'success': False,
                'error': 'No metadata found'
            }), 404
        
        # Merge metadata and save book
        merged = enrichment_service.merge_metadata_into_book(book_data, metadata)
        
        # Update book with enriched data
        updates = {}
        if merged.get('description') and not book_data.get('description'):
            updates['description'] = merged['description']
        if merged.get('cover_url') and merged['cover_url'].strip():
            updates['cover_url'] = merged['cover_url']
        if merged.get('publisher') and not book_data.get('publisher'):
            updates['publisher'] = merged['publisher']
        
        # Update ISBN if missing
        if merged.get('isbn13') and not book_data.get('isbn13'):
            updates['isbn13'] = merged['isbn13']
        if merged.get('isbn10') and not book_data.get('isbn10'):
            updates['isbn10'] = merged['isbn10']
        
        # Update page_count if missing
        if merged.get('page_count') and not book_data.get('page_count'):
            updates['page_count'] = merged['page_count']
        
        # Update language for Bulgarian books
        title = merged.get('title', '') or book_data.get('title', '')
        author = merged.get('author', '') or book_data.get('author', '')
        has_cyrillic_title = any('\u0400' <= char <= '\u04FF' for char in title)
        has_cyrillic_author = any('\u0400' <= char <= '\u04FF' for char in author)
        
        if has_cyrillic_title and has_cyrillic_author:
            current_language = book_data.get('language', '')
            if current_language != 'bg':
                updates['language'] = 'bg'
                current_app.logger.info(f"🌍 Setting language to 'bg' for Bulgarian book: {title}")
        
        # Download and save cover if found
        cover_downloaded = False
        if merged.get('cover_url') and merged['cover_url'].strip():
            try:
                from app.utils.image_processing import process_image_from_url
                cover_url = merged['cover_url']
                if cover_url.startswith('http://') or cover_url.startswith('https://'):
                    local_cover = process_image_from_url(cover_url)
                    if local_cover:
                        updates['cover_url'] = local_cover
                        cover_downloaded = True
            except Exception as e:
                current_app.logger.warning(f"Failed to download cover: {e}")
        
        # Save updates
        if updates:
            # Use the book ID from book_data (handles both dict and object formats)
            update_book_id = book_data.get('id') or book_data.get('uid') or book_id
            update_coro = book_service.update_book(update_book_id, updates)
            run_async(update_coro)
        
        # Build detailed status information
        enriched_fields = []
        if 'description' in updates:
            enriched_fields.append('описание')
        if 'cover_url' in updates:
            enriched_fields.append('обложка')
        if 'publisher' in updates:
            enriched_fields.append('издателство')
        if 'isbn13' in updates or 'isbn10' in updates:
            enriched_fields.append('ISBN')
        if 'page_count' in updates:
            enriched_fields.append('брой страници')
        if 'language' in updates:
            enriched_fields.append('език')
        
        # Check what was found in metadata (even if not updated)
        found_fields = []
        if metadata.get('description'):
            found_fields.append('описание')
        if metadata.get('cover_url'):
            found_fields.append('обложка')
        if metadata.get('publisher'):
            found_fields.append('издателство')
        if metadata.get('isbn') or merged.get('isbn13') or merged.get('isbn10'):
            found_fields.append('ISBN')
        if metadata.get('year'):
            found_fields.append('година на издаване')
        if metadata.get('pages'):
            found_fields.append('брой страници')
        # Check if Bulgarian language was detected
        if has_cyrillic_title and has_cyrillic_author:
            found_fields.append('език (български)')
        
        return jsonify({
            'success': True,
            'metadata': metadata,
            'updates': updates,
            'cover_downloaded': cover_downloaded,
            'quality_score': metadata.get('quality_score', 0),
            'enriched_fields': enriched_fields,
            'found_fields': found_fields,
            'cover_found': bool(metadata.get('cover_url')),
            'description_found': bool(metadata.get('description'))
        })
        
    except Exception as e:
        current_app.logger.error(f"Error enriching book: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@metadata_bp.route('/templates/<template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    """Delete an import mapping template."""
    try:
        template = import_mapping_service.get_template_by_id_sync(template_id)
        if not template:
            flash('Template not found', 'error')
            return redirect(url_for('metadata.templates'))
        
        # Prevent deletion of system templates
        if template.user_id == '__system__':
            flash('System default templates cannot be deleted', 'error')
            return redirect(url_for('metadata.templates'))
        
        # Check ownership
        if template.user_id != current_user.id:
            flash('You can only delete your own templates', 'error')
            return redirect(url_for('metadata.templates'))
        
        # Delete template
        import_mapping_service.delete_template_sync(template_id, current_user.id)
        
        flash(f'Template "{template.name}" deleted successfully!', 'success')
        
    except Exception as e:
        flash(f'Error deleting template: {str(e)}', 'error')
    
    return redirect(url_for('metadata.templates'))
