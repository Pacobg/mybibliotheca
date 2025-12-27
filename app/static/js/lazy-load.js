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
                        img.src = img.dataset.src;
                        img.classList.remove('lazy', 'lazy-loading');
                        img.classList.add('lazy-loaded');
                        
                        // Remove data-src to prevent reloading
                        img.removeAttribute('data-src');
                    };
                    
                    imageLoader.onerror = function() {
                        img.classList.remove('lazy-loading');
                        img.classList.add('lazy-error');
                        console.warn('Failed to load image:', img.dataset.src);
                    };
                    
                    // Start loading
                    imageLoader.src = img.dataset.src;
                }
                
                // Stop observing this image
                observer.unobserve(img);
            }
        });
    }, config);

    // Observe all lazy images
    function observeLazyImages() {
        const lazyImages = document.querySelectorAll('img.lazy');
        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
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

    // Expose function for manual triggering (useful for dynamic content)
    window.lazyLoadImages = observeLazyImages;

    console.log('✅ Lazy loading initialized');
})();
