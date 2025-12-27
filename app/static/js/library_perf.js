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
      
      // Use fetch with keepalive instead of link prefetch to avoid browser warnings
      // This prefetches the data into browser cache without creating a link tag
      // Only prefetch if user is likely to navigate (after a delay)
      fetch(url.toString(), { 
        method: 'GET',
        credentials: 'same-origin',
        keepalive: true,
        cache: 'default'
      }).catch(function() { 
        // Silently fail - prefetch is optional optimization
      });
    } catch (e) {
      // Silently fail - prefetch is optional optimization
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      enhanceCovers();
      // Schedule JSON prefetch after render and user interaction to avoid warnings
      // Only prefetch if user hovers over next button or after 2 seconds
      var nextBtn = document.getElementById('nextPageBtn');
      if (nextBtn && !nextBtn.classList.contains('disabled')) {
        // Prefetch on hover over next button
        nextBtn.addEventListener('mouseenter', function() {
          prefetchNextPageJSON();
        }, { once: true });
        
        // Also prefetch after 2 seconds if user hasn't navigated
        setTimeout(prefetchNextPageJSON, 2000);
      }
    });
  } else {
    enhanceCovers();
    var nextBtn = document.getElementById('nextPageBtn');
    if (nextBtn && !nextBtn.classList.contains('disabled')) {
      nextBtn.addEventListener('mouseenter', function() {
        prefetchNextPageJSON();
      }, { once: true });
      setTimeout(prefetchNextPageJSON, 2000);
    }
  }
})();
