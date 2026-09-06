document.addEventListener('DOMContentLoaded', function () {

    // ===== Sidebar Toggle (mobile & tablet) =====
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    function toggleSidebar() {
        if (sidebar) {
            sidebar.classList.toggle('show');
            if (sidebarBackdrop) {
                sidebarBackdrop.classList.toggle('show');
            }
        }
    }

    function closeSidebar() {
        if (sidebar && sidebar.classList.contains('show')) {
            sidebar.classList.remove('show');
            if (sidebarBackdrop) {
                sidebarBackdrop.classList.remove('show');
            }
        }
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function (e) {
            e.stopPropagation();
            toggleSidebar();
        });
    }

    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', closeSidebar);
    }

    // Close sidebar when clicking any nav link on mobile/tablet
    if (sidebar) {
        sidebar.querySelectorAll('.nav-link').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth <= 992) {
                    closeSidebar();
                }
            });
        });
    }

    // ===== Auto-calculate Amount = Quantity × Rate =====
    const qtyInput = document.getElementById('quantity_mt');
    const rateInput = document.getElementById('rate');
    const amountInput = document.getElementById('amount');

    function calcAmount() {
        if (qtyInput && rateInput && amountInput) {
            const qty = parseFloat(qtyInput.value) || 0;
            const rate = parseFloat(rateInput.value) || 0;
            amountInput.value = (qty * rate).toFixed(2);
        }
    }

    if (qtyInput) qtyInput.addEventListener('input', calcAmount);
    if (rateInput) rateInput.addEventListener('input', calcAmount);

    // ===== Delete Confirmation =====
    document.querySelectorAll('.btn-delete').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm('Are you sure you want to delete this record? This cannot be undone.')) {
                e.preventDefault();
            }
        });
    });

    // ===== Set today as default date =====
    document.querySelectorAll('input[type="date"]').forEach(function (input) {
        if (!input.value && !input.dataset.noDefault) {
            input.value = new Date().toISOString().split('T')[0];
        }
    });

    // ===== Auto-dismiss flash alerts =====
    document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
        setTimeout(function () {
            if (alert && alert.parentNode) {
                var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // ===== Format currency inputs =====
    document.querySelectorAll('.currency-display').forEach(function (el) {
        const value = parseFloat(el.textContent);
        if (!isNaN(value)) {
            el.textContent = '₹' + value.toLocaleString('en-IN', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }
    });

    // ===== Print button =====
    document.querySelectorAll('.btn-print').forEach(function (btn) {
        btn.addEventListener('click', function () {
            window.print();
        });
    });

    // ===== Disable mouse wheel scroll value changes on all inputs =====
    document.addEventListener('wheel', function (e) {
        if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.type === 'number')) {
            document.activeElement.blur();
        }
    });

});
