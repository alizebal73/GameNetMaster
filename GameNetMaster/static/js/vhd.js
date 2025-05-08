// VHD Management JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize VHD Management page functionality
    initializeVhdPage();
    
    // Set up VHD detail modals
    setupVhdDetailModals();
    
    // Set up VHD search
    setupVhdSearch();
});

// Initialize VHD management page
function initializeVhdPage() {
    // Handle new VHD form validation
    const newVhdForm = document.getElementById('newVhdForm');
    if (newVhdForm) {
        newVhdForm.addEventListener('submit', function(e) {
            const nameInput = document.getElementById('vhdName');
            const sizeInput = document.getElementById('vhdSize');
            
            if (!nameInput.value.trim()) {
                e.preventDefault();
                alert('Please enter a VHD name');
                nameInput.focus();
                return;
            }
            
            const size = parseFloat(sizeInput.value);
            if (isNaN(size) || size <= 0) {
                e.preventDefault();
                alert('Please enter a valid VHD size (greater than 0)');
                sizeInput.focus();
                return;
            }
        });
    }
    
    // Handle edit VHD forms
    document.querySelectorAll('.edit-vhd-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const nameInput = this.querySelector('input[name="name"]');
            if (!nameInput.value.trim()) {
                e.preventDefault();
                alert('VHD name cannot be empty');
                nameInput.focus();
            }
        });
    });
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Set up VHD detail modals
function setupVhdDetailModals() {
    // Add click handlers for detail buttons
    document.querySelectorAll('.btn-vhd-detail').forEach(btn => {
        btn.addEventListener('click', function() {
            const vhdId = this.getAttribute('data-vhd-id');
            const vhdName = this.getAttribute('data-vhd-name');
            const vhdDesc = this.getAttribute('data-vhd-desc') || '';
            const vhdSize = this.getAttribute('data-vhd-size');
            const vhdPath = this.getAttribute('data-vhd-path');
            const vhdWindows = this.getAttribute('data-vhd-windows') || 'Unknown';
            const vhdTemplate = this.getAttribute('data-vhd-template') === 'true';
            const vhdLocked = this.getAttribute('data-vhd-locked') === 'true';
            const vhdCreated = this.getAttribute('data-vhd-created');
            const vhdModified = this.getAttribute('data-vhd-modified');
            
            // Update modal content
            document.getElementById('vhdDetailTitle').textContent = vhdName;
            
            const detailHtml = `
                <div class="card mb-3">
                    <div class="card-header">
                        <h5 class="mb-0">VHD Information</h5>
                    </div>
                    <div class="card-body">
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Description:</div>
                            <div class="col-md-8">${vhdDesc || 'No description'}</div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Size:</div>
                            <div class="col-md-8">${vhdSize} GB</div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Windows Version:</div>
                            <div class="col-md-8">${vhdWindows}</div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">File Path:</div>
                            <div class="col-md-8"><code>${vhdPath}</code></div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Template:</div>
                            <div class="col-md-8">
                                ${vhdTemplate ? 
                                    '<span class="badge bg-info">Yes</span>' : 
                                    '<span class="badge bg-secondary">No</span>'}
                            </div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Locked:</div>
                            <div class="col-md-8">
                                ${vhdLocked ? 
                                    '<span class="badge bg-danger">Yes</span>' : 
                                    '<span class="badge bg-success">No</span>'}
                            </div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Created:</div>
                            <div class="col-md-8">${formatDateTime(vhdCreated)}</div>
                        </div>
                        <div class="row mb-2">
                            <div class="col-md-4 fw-bold">Last Modified:</div>
                            <div class="col-md-8">${formatDateTime(vhdModified)}</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Actions</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-flex flex-wrap gap-2">
                            <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#editVhdModal${vhdId}">
                                <i class="fas fa-edit me-1"></i> Edit
                            </button>
                            
                            <button type="button" class="btn btn-success" onclick="showCloneVhdModal(${vhdId}, '${vhdName}')">
                                <i class="fas fa-copy me-1"></i> Clone
                            </button>
                            
                            ${!vhdLocked ? `
                                <button type="button" class="btn btn-danger" onclick="confirmDeleteVhd(${vhdId}, '${vhdName}')">
                                    <i class="fas fa-trash-alt me-1"></i> Delete
                                </button>
                            ` : `
                                <button type="button" class="btn btn-danger" disabled title="Cannot delete locked VHD">
                                    <i class="fas fa-trash-alt me-1"></i> Delete
                                </button>
                            `}
                        </div>
                    </div>
                </div>
            `;
            
            document.getElementById('vhdDetailContent').innerHTML = detailHtml;
            
            // Show the modal
            const vhdModal = new bootstrap.Modal(document.getElementById('vhdDetailModal'));
            vhdModal.show();
        });
    });
}

// Set up VHD search functionality
function setupVhdSearch() {
    const searchInput = document.getElementById('vhdSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            filterVhds(searchTerm);
        });
    }
}

// Filter VHDs based on search term
function filterVhds(searchTerm) {
    const vhdRows = document.querySelectorAll('#vhdTable tbody tr');
    
    vhdRows.forEach(row => {
        const name = row.querySelector('td:nth-child(1)').textContent.toLowerCase();
        const desc = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
        const windows = row.querySelector('td:nth-child(3)').textContent.toLowerCase();
        
        if (name.includes(searchTerm) || desc.includes(searchTerm) || windows.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Format date and time
function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return 'Unknown';
    
    const date = new Date(dateTimeStr);
    return date.toLocaleString();
}

// Show clone VHD modal
function showCloneVhdModal(vhdId, vhdName) {
    document.getElementById('cloneSourceId').value = vhdId;
    document.getElementById('cloneSourceName').textContent = vhdName;
    document.getElementById('newVhdName').value = `Clone of ${vhdName}`;
    
    const cloneModal = new bootstrap.Modal(document.getElementById('cloneVhdModal'));
    cloneModal.show();
}

// Confirm VHD deletion
function confirmDeleteVhd(vhdId, vhdName) {
    if (confirm(`Are you sure you want to delete VHD "${vhdName}"? This action cannot be undone.`)) {
        // Create and submit a form to delete the VHD
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/vhd/delete/${vhdId}`;
        document.body.appendChild(form);
        form.submit();
    }
}
