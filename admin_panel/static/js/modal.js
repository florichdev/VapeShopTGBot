class ModalManager {
    constructor() {
        this.modals = new Map();
        this.init();
    }

    init() {
        document.addEventListener('click', (event) => {
            if (event.target.classList.contains('modal')) {
                this.hide(event.target.id);
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                this.hideAll();
            }
        });
    }

    register(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            this.modals.set(modalId, modal);
            
            const closeButtons = modal.querySelectorAll('.close');
            closeButtons.forEach(btn => {
                btn.addEventListener('click', () => this.hide(modalId));
            });
        }
    }

    show(modalId) {
        const modal = this.modals.get(modalId);
        if (modal) {
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden';
        }
    }

    hide(modalId) {
        const modal = this.modals.get(modalId);
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    hideAll() {
        this.modals.forEach(modal => {
            modal.style.display = 'none';
        });
        document.body.style.overflow = '';
    }
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        document.body.classList.add('modal-open');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.classList.remove('modal-open');
    }
}

document.addEventListener('click', function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target === modal) {
            closeModal(modal.id);
        }
    });
});

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal[style="display: block;"]');
        openModals.forEach(modal => {
            closeModal(modal.id);
        });
    }
});

window.modalManager = new ModalManager();

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.modal').forEach(modal => {
        window.modalManager.register(modal.id);
    });
});