// Modern Task Manager JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('main-content');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const menuToggle = document.getElementById('menu-toggle');
    const sidebarClose = document.getElementById('sidebar-close');
    const themeToggle = document.getElementById('theme-toggle');
    const searchInput = document.getElementById('search-input');
    const body = document.body;

    // Sidebar Toggle Functionality
    function toggleSidebar() {
        const isCollapsed = sidebar.classList.contains('collapsed');

        if (window.innerWidth <= 768) {
            // Mobile behavior
            sidebar.classList.toggle('collapsed');
            sidebarOverlay.classList.toggle('active');
        } else {
            // Desktop behavior
            sidebar.classList.toggle('collapsed');
            mainContent.classList.toggle('expanded');
        }
    }

    // Event Listeners
    if (menuToggle) {
        menuToggle.addEventListener('click', toggleSidebar);
    }

    if (sidebarClose) {
        sidebarClose.addEventListener('click', toggleSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', toggleSidebar);
    }

    // Theme Toggle Functionality
    function toggleTheme() {
        const isDark = body.classList.contains('theme-dark');

        if (isDark) {
            body.classList.remove('theme-dark');
            localStorage.setItem('theme', 'light');
            updateThemeIcon(false);
        } else {
            body.classList.add('theme-dark');
            localStorage.setItem('theme', 'dark');
            updateThemeIcon(true);
        }
    }

    function updateThemeIcon(isDark) {
        if (themeToggle) {
            themeToggle.innerHTML = isDark ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>';
        }
    }

    // Load saved theme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        body.classList.add('theme-dark');
        updateThemeIcon(true);
    } else {
        updateThemeIcon(false);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // Search Functionality
    let searchTimeout;
    function handleSearch() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            const query = searchInput.value.toLowerCase().trim();
            const taskCards = document.querySelectorAll('.task-card');

            taskCards.forEach(card => {
                const title = card.querySelector('.task-title')?.textContent.toLowerCase() || '';
                const description = card.querySelector('.task-description')?.textContent.toLowerCase() || '';
                const badges = Array.from(card.querySelectorAll('.badge')).map(badge =>
                    badge.textContent.toLowerCase()
                ).join(' ');

                const searchableText = `${title} ${description} ${badges}`;

                if (searchableText.includes(query) || query === '') {
                    card.style.display = 'block';
                    card.classList.add('fade-in');
                } else {
                    card.style.display = 'none';
                    card.classList.remove('fade-in');
                }
            });
        }, 300);
    }

    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
    }

    // Task Actions
    function initializeTaskActions() {
        // Complete/Incomplete toggle
        document.querySelectorAll('.task-complete-toggle').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const taskId = this.dataset.taskId;
                const taskCard = this.closest('.task-card');
                const statusBadge = taskCard.querySelector('.badge-status');

                // Toggle status
                if (statusBadge.textContent.includes('Done')) {
                    statusBadge.textContent = 'In Progress';
                    statusBadge.className = 'badge badge-warning';
                    this.textContent = 'Complete';
                    this.className = 'btn btn-sm btn-outline-success';
                } else {
                    statusBadge.textContent = 'Done';
                    statusBadge.className = 'badge badge-status';
                    this.textContent = 'Undo';
                    this.className = 'btn btn-sm btn-outline-secondary';
                }

                // Add animation
                taskCard.classList.add('fade-in');
                setTimeout(() => taskCard.classList.remove('fade-in'), 300);
            });
        });

        // Delete confirmation
        document.querySelectorAll('.task-delete').forEach(button => {
            button.addEventListener('click', function(e) {
                if (!confirm('Are you sure you want to delete this task?')) {
                    e.preventDefault();
                }
            });
        });
    }

    initializeTaskActions();

    // Progress Bar Animation
    function animateProgressBars() {
        const progressBars = document.querySelectorAll('.progress-fill');

        progressBars.forEach(bar => {
            const width = bar.style.width || '0%';
            bar.style.width = '0%';

            setTimeout(() => {
                bar.style.width = width;
            }, 100);
        });
    }

    animateProgressBars();

    // Smooth Scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Keyboard Shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K for search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
            }
        }

        // Escape to close sidebar on mobile
        if (e.key === 'Escape' && window.innerWidth <= 768) {
            sidebar.classList.add('collapsed');
            sidebarOverlay.classList.remove('active');
        }
    });

    // Window Resize Handler
    function handleResize() {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('collapsed');
            sidebarOverlay.classList.remove('active');
            mainContent.classList.remove('expanded');
        } else {
            sidebar.classList.add('collapsed');
            mainContent.classList.add('expanded');
        }
    }

    window.addEventListener('resize', handleResize);

    // Initial setup
    handleResize();

    // Add loading states
    function showLoading(element) {
        element.classList.add('loading');
    }

    function hideLoading(element) {
        element.classList.remove('loading');
    }

    // Form validation
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
            }
        });
    });

    // Notification system
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        `;

        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => notification.classList.add('show'), 10);

        // Auto remove
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);

        // Manual close
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        });
    }

    // Make showNotification globally available
    window.showNotification = showNotification;

    // Initialize tooltips (if using Bootstrap tooltips)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    if (typeof bootstrap !== 'undefined') {
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Performance optimization: Lazy load images
    const images = document.querySelectorAll('img[data-src]');
    const imageObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                observer.unobserve(img);
            }
        });
    });

    images.forEach(img => imageObserver.observe(img));

    // Accessibility improvements
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });

    // Focus management for modals (if any)
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            const focusableElements = document.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === firstElement) {
                    lastElement.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === lastElement) {
                    firstElement.focus();
                    e.preventDefault();
                }
            }
        }
    });
});
