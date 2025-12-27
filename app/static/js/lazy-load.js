/**
 * Lazy Loading for Book Covers
 * 
 * Loads images only when they're about to enter the viewport.
 * Dramatically reduces initial page load time.
 * 
 * Usage:
 * - Add class="lazy" to img tags
 * - Use data-src instead of src for the image URL
 * - Include a placeholder image in src
 */

(function() {
    'use strict';

    // Check if IntersectionObserver is supported
    if (!('IntersectionObserver' in window)) {
        // Fallback: load all images immediately
        console.warn('IntersectionObserver not supported, loading all images');
        const lazyImages = document.querySelectorAll('img.lazy');
        lazyImages.forEach(img => {
            if (img.dataset.src) {
                img.src = img.dataset.src;
                img.classList.remove('lazy');
            }
        });
        return;
    }

    // Configuration
    const config = {
        rootMargin: '50px 0px', // Start loading 50px before image enters viewport
        threshold: 0.01
    };

    // Create observer
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                
                // Load image
                if (img.dataset.src) {
                    // Add loading class
                    img.classList.add('lazy-loading');
                    
                    // Create new image to preload
                    const imageLoader = new Image();
                    
                    imageLoader.onload = function() {
                        // Success - update actual image
                        img.src = img.dataset.src;
                        img.classList.remove('lazy', 'lazy-loading');
                        img.classList.add('lazy-loaded');
                        loadedImages.add(img.dataset.src);
                        
                        // Remove data-src to prevent reloading
                        img.removeAttribute('data-src');
                        
                        console.log(`✅ Loaded: ${img.dataset.src.substring(0, 50)}...`);
                    };
                    
                    imageLoader.onerror = function() {
                        img.classList.remove('lazy-loading');
                        img.classList.add('lazy-error');
                        
                        // Fallback to default placeholder
                        if (img.dataset.src) {
                            img.src = '/static/bookshelf.png';
                            img.removeAttribute('data-src');
                        }
                        
                        console.warn(`⚠️  Failed to load image: ${img.dataset.src}`);
                    };
                    
                    // Start loading
                    imageLoader.src = img.dataset.src;
                }
                
                // Stop observing this image
                observer.unobserve(img);
            }
        });
    }, config);

    // Track loaded images to prevent duplicates
    const loadedImages = new Set();
    
    // Observe all lazy images
    function observeLazyImages() {
        const lazyImages = document.querySelectorAll('img.lazy, img[loading="lazy"]');
        
        if (lazyImages.length === 0) {
            console.log('ℹ️  No lazy images found');
            return;
        }
        
        lazyImages.forEach(img => {
            // Set placeholder if not already set
            if (!img.src || img.src === window.location.href) {
                img.src = '/static/default-book-cover.svg';
            }
            
            // Add loading class
            if (!img.classList.contains('lazy-loading')) {
                img.classList.add('lazy-loading');
            }
            
            // Observe image
            imageObserver.observe(img);
        });
        
        console.log(`✅ Lazy loading initialized for ${lazyImages.length} images`);
    }

    // Initial observation
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', observeLazyImages);
    } else {
        observeLazyImages();
    }

    // Re-observe when new content is added (e.g., pagination, search results)
    const originalPushState = history.pushState;
    history.pushState = function() {
        originalPushState.apply(history, arguments);
        setTimeout(observeLazyImages, 100);
    };

    const originalReplaceState = history.replaceState;
    history.replaceState = function() {
        originalReplaceState.apply(history, arguments);
        setTimeout(observeLazyImages, 100);
    };

    // Also observe on popstate (back/forward navigation)
    window.addEventListener('popstate', () => {
        setTimeout(observeLazyImages, 100);
    });

    /**
     * Handle dynamic content (infinite scroll, AJAX)
     */
    function observeNewImages() {
        // Watch for new images added to DOM
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) { // Element node
                        // Check if node itself is lazy image
                        if (node.matches && node.matches('img.lazy, img[loading="lazy"]')) {
                            if (!node.src || node.src === window.location.href) {
                                node.src = '/static/default-book-cover.svg';
                            }
                            node.classList.add('lazy-loading');
                            imageObserver.observe(node);
                        }
                        
                        // Check for lazy images within node
                        const lazyImages = node.querySelectorAll && node.querySelectorAll('img.lazy, img[loading="lazy"]');
                        if (lazyImages && lazyImages.length > 0) {
                            lazyImages.forEach(img => {
                                if (!img.src || img.src === window.location.href) {
                                    img.src = '/static/default-book-cover.svg';
                                }
                                img.classList.add('lazy-loading');
                                imageObserver.observe(img);
                            });
                        }
                    }
                });
            });
        });
        
        // Observe document body for changes
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        console.log('✅ Observing for dynamically added images');
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            observeLazyImages();
            observeNewImages();
        });
    } else {
        observeLazyImages();
        observeNewImages();
    }
    
    // Expose function for manual triggering (useful for dynamic content)
    window.lazyLoadImages = observeLazyImages;
    
    // Log stats on page unload (for debugging)
    window.addEventListener('beforeunload', () => {
        console.log(`📊 Lazy loading stats: ${loadedImages.size} images loaded`);
    });
})();
