// ===== Wait for DOM to be fully loaded =====
document.addEventListener('DOMContentLoaded', function () {

    // ===== Auto-hide alerts after 5 seconds =====
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                alert.remove();
            }, 300);
        }, 5000);
    });

    // ===== Show notification =====
    window.showNotification = function (message, type = 'success') {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            ${message}
            <button class="alert-close" onclick="this.parentElement.remove()">×</button>
        `;

        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alert, container.firstChild);

            setTimeout(() => {
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-10px)';
                setTimeout(() => {
                    alert.remove();
                }, 300);
            }, 5000);
        }
    };

    // ===== Number formatting =====
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        if (input.step === '0.01') {
            input.addEventListener('blur', function () {
                if (this.value) {
                    this.value = parseFloat(this.value).toFixed(2);
                }
            });
        }
    });

    // ===== Confirm delete actions =====
    const deleteLinks = document.querySelectorAll('a[href*="delete"]');
    deleteLinks.forEach(link => {
        if (!link.hasAttribute('onclick')) {
            link.addEventListener('click', function (e) {
                if (!confirm('Are you sure you want to delete this item?')) {
                    e.preventDefault();
                }
            });
        }
    });

    // ===== Add active class to current nav link =====
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.style.background = 'var(--dark-hover)';
            link.style.color = 'var(--primary-light)';
        }
    });

    // ===== Auto-update progress bars =====
    const progressBars = document.querySelectorAll('.progress-fill');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0%';
        setTimeout(() => {
            bar.style.width = width;
        }, 100);
    });

    // ===== Console welcome message =====
    console.log('%c💰 FinTrackr', 'font-size: 24px; font-weight: bold; color: #6366f1;');
    console.log('%cPersonal Finance Management System', 'font-size: 14px; color: #8b5cf6;');
    console.log('%cManage your finances with ease!', 'font-size: 12px; color: #94a3b8;');
});

// ===== Smooth scroll to top =====
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// ===== Format currency inputs =====
function formatCurrency(input) {
    let value = input.value.replace(/[^0-9.]/g, '');
    const parts = value.split('.');
    if (parts.length > 2) {
        value = parts[0] + '.' + parts.slice(1).join('');
    }
    if (parts[1] && parts[1].length > 2) {
        value = parts[0] + '.' + parts[1].substring(0, 2);
    }
    input.value = value;
}

// ===== Mobile menu toggle (if needed in future) =====
function toggleMobileMenu() {
    const navMenu = document.querySelector('.nav-menu');
    if (navMenu) {
        navMenu.classList.toggle('active');
    }
}
