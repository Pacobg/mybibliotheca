// Lightweight client-side optimizations for Library initial paint and navigation
(function() {
  function enhanceCovers() {
    var imgs = document.querySelectorAll('.book-cover-wrapper img');
    if (!imgs || !imgs.length) return;
    for (var i = 0; i < imgs.length; i++) {
      var img = imgs[i];
      // Prioritize the first couple of covers for faster visual feedback
      if (i < 2) {
        img.setAttribute('fetchpriority', 'high');
        img.setAttribute('loading', 'eager');
      } else {
        // Defer everything else; decoding async reduces main-thread jank
        if (!img.hasAttribute('loading')) img.setAttribute('loading', 'lazy');
        img.setAttribute('decoding', 'async');
        // Add a low-priority hint if supported
        img.setAttribute('fetchpriority', 'low');
      }
    }
  }

  function prefetchNextPageJSON() {
    // Disabled to avoid browser warnings
    // Prefetching is handled by browser cache naturally when user navigates
    return;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      enhanceCovers();
      // Prefetch disabled to avoid browser warnings
      // Browser cache will handle prefetching naturally when user navigates
    });
  } else {
    enhanceCovers();
  }
})();
