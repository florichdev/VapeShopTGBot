class ProductManager {
    constructor() {
        this.products = new Map();
        this.init();
    }

    init() {
        this.loadProducts();
        this.setupEventListeners();
    }

    loadProducts() {
        document.querySelectorAll('[data-product-id]').forEach(row => {
            const productId = row.getAttribute('data-product-id');
            this.products.set(productId, {
                id: productId,
                name: row.getAttribute('data-product-name'),
                description: row.getAttribute('data-product-description'),
                price: parseFloat(row.getAttribute('data-product-price')),
                photo: row.getAttribute('data-product-photo'),
                external: row.getAttribute('data-product-external'),
                active: row.getAttribute('data-product-active') === 'True',
                category: row.getAttribute('data-product-category')
            });
        });
    }

    setupEventListeners() {
        document.querySelectorAll('.btn-edit').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const productId = e.target.closest('tr').getAttribute('data-product-id');
                this.editProduct(productId);
            });
        });

        document.querySelector('.btn-primary').addEventListener('click', () => {
            this.addProduct();
        });
    }

    editProduct(productId) {
        const product = this.products.get(productId);
        if (!product) return;

        document.getElementById('editProductId').value = product.id;
        document.getElementById('editName').value = product.name;
        document.getElementById('editDescription').value = product.description;
        document.getElementById('editPrice').value = product.price.toFixed(2);
        document.getElementById('editPhoto').value = product.photo || '';
        document.getElementById('editExternalUrl').value = product.external || '';
        document.getElementById('editActive').checked = product.active;

        const categorySelect = document.getElementById('editCategory');
        categorySelect.value = product.category;

        const editForm = document.getElementById('editForm');
        editForm.action = `/products/edit/${product.id}`;
        
        this.showModal('editProductModal');
    }

    addProduct() {
        document.querySelector('#addProductModal form').reset();
        document.getElementById('addProductModal').querySelector('[name="is_active"]').checked = true;
        
        this.showModal('addProductModal');
    }

    showModal(modalId) {
        document.getElementById(modalId).style.display = 'block';
        document.body.classList.add('modal-open');
    }

    closeModal(modalId) {
        document.getElementById(modalId).style.display = 'none';
        document.body.classList.remove('modal-open');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const externalUrlInput = document.getElementById('editExternalUrl');
    const activeCheckbox = document.getElementById('editActive');
    const activeLabel = document.getElementById('activeLabel');
    
    if (externalUrlInput && activeCheckbox && activeLabel) {
        externalUrlInput.addEventListener('input', function() {
            if (this.value.trim() !== '') {
                activeLabel.innerHTML = 'Активировать принудительно (ссылка указана)';
                activeCheckbox.checked = false;
            } else {
                activeLabel.innerHTML = 'Активировать без проверки (не рекомендуется)';
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    window.productManager = new ProductManager();
});