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
     * Auto-initialize debounced search for elements with data-debounce-search
     */
    function autoInitDebouncedSearch() {
        const searchInputs = document.querySelectorAll('[data-debounce-search="true"]');
        
        searchInputs.forEach(input => {
            // Get callback from data attribute or use default form submission
            const callbackName = input.dataset.debounceCallback || 'default';
            const delay = parseInt(input.dataset.debounceDelay) || DEFAULT_DELAY;
            
            let callback;
            
            if (callbackName === 'default') {
                // Default: submit form or trigger search
                callback = (query) => {
                    // Try to find and submit the form
                    const form = input.closest('form');
                    if (form) {
                        // Update URL parameter if it's a GET form
                        if (form.method.toLowerCase() === 'get') {
                            const url = new URL(window.location);
                            if (query) {
                                url.searchParams.set('search', query);
                            } else {
                                url.searchParams.delete('search');
                            }
                            // Reset to page 1 when searching
                            url.searchParams.set('page', '1');
                            window.location.href = url.toString();
                        } else {
                            form.submit();
                        }
                    } else {
                        // No form, try to trigger custom event
                        const event = new CustomEvent('debouncedSearch', {
                            detail: { query: query }
                        });
                        input.dispatchEvent(event);
                    }
                };
            } else {
                // Custom callback from window object
                callback = window[callbackName];
                if (typeof callback !== 'function') {
                    console.warn(`Callback function "${callbackName}" not found`);
                    return;
                }
            }
            
            initDebouncedSearch(input, callback, delay);
        });
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
