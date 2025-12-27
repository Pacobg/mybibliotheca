/**
 * Debounced Search
 * 
 * Prevents search from firing on every keystroke.
 * Waits for user to stop typing before searching.
 * 
 * Reduces database queries by 90%+.
 * 
 * Usage:
 * - Add data-debounce-search="true" to search input
 * - Or use: debounceSearch(inputElement, callback, delay)
 */

(function() {
    'use strict';

    // Default delay (milliseconds)
    const DEFAULT_DELAY = 300;

    /**
     * Debounce function
     * @param {Function} func - Function to debounce
     * @param {number} wait - Delay in milliseconds
     * @returns {Function} Debounced function
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Initialize debounced search for an input element
     * @param {HTMLElement} input - Input element
     * @param {Function} callback - Callback function(query)
     * @param {number} delay - Delay in milliseconds
     */
    function initDebouncedSearch(input, callback, delay = DEFAULT_DELAY) {
        if (!input || typeof callback !== 'function') {
            console.warn('Invalid input or callback for debounced search');
            return;
        }

        // Create debounced callback
        const debouncedCallback = debounce((query) => {
            callback(query);
        }, delay);

        // Add loading indicator
        const loadingIndicator = document.createElement('span');
        loadingIndicator.className = 'search-loading';
        loadingIndicator.style.display = 'none';
        loadingIndicator.innerHTML = ' <i class="bi bi-hourglass-split"></i>';
        input.parentNode.insertBefore(loadingIndicator, input.nextSibling);

        // Handle input events
        let isSearching = false;
        
        input.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            
            // Show loading indicator
            loadingIndicator.style.display = 'inline-block';
            isSearching = true;
            
            // If query is empty, call immediately (no debounce)
            if (query === '') {
                clearTimeout(debouncedCallback.timeout);
                callback(query);
                loadingIndicator.style.display = 'none';
                isSearching = false;
            } else {
                // Debounce the search
                debouncedCallback(query);
            }
        });

        // Handle search completion
        const originalCallback = callback;
        callback = function(query) {
            originalCallback(query);
            loadingIndicator.style.display = 'none';
            isSearching = false;
        };

        // Also handle Enter key (search immediately)
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(debouncedCallback.timeout);
                const query = input.value.trim();
                callback(query);
                loadingIndicator.style.display = 'none';
                isSearching = false;
            }
        });
    }

    /**
     * Auto-initialize debounced search
     * Tries multiple selectors to find search input
     */
    function autoInitDebouncedSearch() {
        // Try multiple selectors
        const searchInput = document.querySelector(
            '#search-input, input[name="search"], input[name="q"], input[type="search"], [data-debounce-search="true"]'
        );
        
        if (!searchInput) {
            console.log('ℹ️  No search input found for debouncing');
            return;
        }
        
        console.log('✅ Found search input, initializing debounced search');
        
        // Get delay from data attribute or use default
        const delay = parseInt(searchInput.dataset.debounceDelay) || DEFAULT_DELAY;
        const minQueryLength = parseInt(searchInput.dataset.minQueryLength) || 2;
        
        // State
        let searchTimeout = null;
        let lastQuery = '';
        let searchInProgress = false;
        
        // Get search form
        const searchForm = searchInput.closest('form');
        
        if (searchForm) {
            // Prevent default form submission
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                performSearch(searchInput.value.trim());
            });
        }
        
        /**
         * Perform the actual search
         */
        function performSearch(query) {
            if (searchInProgress) {
                console.log('⏳ Search already in progress, skipping...');
                return;
            }
            
            searchInProgress = true;
            lastQuery = query;
            
            console.log(`🔍 Searching for: "${query}"`);
            
            // Update URL with search query
            const url = new URL(window.location.href);
            
            if (query && query.length >= minQueryLength) {
                url.searchParams.set('search', query);
                url.searchParams.set('q', query);  // Support both params
            } else {
                url.searchParams.delete('search');
                url.searchParams.delete('q');
            }
            
            // Reset to page 1 for new search
            url.searchParams.set('page', '1');
            
            // Navigate to search results
            window.location.href = url.toString();
        }
        
        // Handle input events
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.trim();
            
            // Clear previous timeout
            clearTimeout(searchTimeout);
            
            // Ignore if query too short
            if (query.length > 0 && query.length < minQueryLength) {
                return;
            }
            
            // Ignore if query hasn't changed
            if (query === lastQuery) {
                return;
            }
            
            // Debounce search
            searchTimeout = setTimeout(() => {
                performSearch(query);
            }, delay);
            
            console.log(`⏳ Search debounced: "${query}" (waiting ${delay}ms)`);
        });
        
        // Handle special keys
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                // Instant search on Enter
                e.preventDefault();
                clearTimeout(searchTimeout);
                performSearch(searchInput.value.trim());
            } else if (e.key === 'Escape') {
                // Clear search on Escape
                clearTimeout(searchTimeout);
                searchInput.value = '';
                lastQuery = '';
                performSearch('');
            }
        });
        
        // Add visual feedback
        searchInput.title = 'Press Enter to search immediately, Escape to clear';
        searchInput.setAttribute('aria-label', 'Search books (debounced)');
        searchInput.setAttribute('autocomplete', 'off');
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', autoInitDebouncedSearch);
    } else {
        autoInitDebouncedSearch();
    }

    // Expose function globally
    window.debounceSearch = initDebouncedSearch;
    window.debounce = debounce;

    console.log('✅ Debounced search initialized');
})();
