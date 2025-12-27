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
    try {
      var container = document.getElementById('books-container');
      if (!container) return;
      var currentPage = parseInt((window.URL || window.webkitURL ? new URL(window.location.href).searchParams.get('page') : (function(){return null;})()) || '1', 10);
      if (isNaN(currentPage) || currentPage < 1) currentPage = 1;
      // Only prefetch if there appears to be a next page button enabled
      var nextBtn = document.getElementById('nextPageBtn');
      if (!nextBtn || nextBtn.classList.contains('disabled')) return;

      var url = new URL(window.location.href);
      url.searchParams.set('page', String(currentPage + 1));
      url.searchParams.set('format', 'json');
      
      // Use prefetch link instead of fetch to avoid credentials warnings
      // Only prefetch if not already prefetched
      var existingPrefetch = document.querySelector('link[rel="prefetch"][href="' + url.toString() + '"]');
      if (existingPrefetch) return;
      
      var link = document.createElement('link');
      link.rel = 'prefetch';
      link.href = url.toString();
      link.as = 'fetch';
      link.crossOrigin = 'same-origin';
      document.head.appendChild(link);
    } catch (e) {
      // Silently fail - prefetch is optional optimization
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      enhanceCovers();
      // Schedule JSON prefetch after render to avoid competing with critical path
      setTimeout(prefetchNextPageJSON, 500);
    });
  } else {
    enhanceCovers();
    setTimeout(prefetchNextPageJSON, 500);
  }
})();
