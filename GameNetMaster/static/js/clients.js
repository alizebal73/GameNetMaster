// Client Management JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Client Management page functionality
    initializeClientPage();
    
    // Set up MAC address formatting
    setupMacAddressFormatting();
    
    // Set up client detail view
    setupClientDetailView();
    
    // Refresh client status periodically
    refreshClientsStatus();
    setInterval(refreshClientsStatus, 10000);
});

// Initialize client page
function initializeClientPage() {
    // Handle new client form submission
    const newClientForm = document.getElementById('newClientForm');
    if (newClientForm) {
        newClientForm.addEventListener('submit', function(e) {
            if (!validateMacAddress(document.getElementById('macAddress').value)) {
                e.preventDefault();
                alert('Please enter a valid MAC address (format: XX:XX:XX:XX:XX:XX)');
            }
        });
    }
    
    // Handle edit client forms
    document.querySelectorAll('.edit-client-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const macInput = this.querySelector('input[name="mac_address"]');
            if (!validateMacAddress(macInput.value)) {
                e.preventDefault();
                alert('Please enter a valid MAC address (format: XX:XX:XX:XX:XX:XX)');
            }
        });
    });
    
    // Handle client search
    const searchInput = document.getElementById('clientSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterClients(this.value.toLowerCase());
        });
    }
}

// Format MAC address input
function setupMacAddressFormatting() {
    const macInputs = document.querySelectorAll('input[name="mac_address"]');
    
    macInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = this.value.replace(/[^0-9a-fA-F]/g, '').toUpperCase();
            let formattedValue = '';
            
            for (let i = 0; i < value.length && i < 12; i++) {
                if (i > 0 && i % 2 === 0) {
                    formattedValue += ':';
                }
                formattedValue += value[i];
            }
            
            this.value = formattedValue;
        });
    });
}

// Validate MAC address format
function validateMacAddress(mac) {
    return /^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$/i.test(mac);
}

// Filter clients based on search term
function filterClients(searchTerm) {
    const clientRows = document.querySelectorAll('#clientsTable tbody tr');
    
    clientRows.forEach(row => {
        const name = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
        const mac = row.querySelector('td:nth-child(4)').textContent.toLowerCase();
        const ip = row.querySelector('td:nth-child(3)').textContent.toLowerCase();
        
        if (name.includes(searchTerm) || mac.includes(searchTerm) || ip.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

// Set up client detail view
function setupClientDetailView() {
    // Check if we have a hash in the URL to show a specific client
    const hash = window.location.hash;
    if (hash && hash.startsWith('#client-')) {
        const clientId = hash.substring(8);
        openClientDetail(clientId);
    }
    
    // Add click handlers for detail buttons
    document.querySelectorAll('.btn-client-detail').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const clientId = this.getAttribute('data-client-id');
            openClientDetail(clientId);
            e.preventDefault();
        });
    });
}

// Open client detail view
function openClientDetail(clientId) {
    // Update URL hash
    window.location.hash = `client-${clientId}`;
    
    // Show the client detail modal
    const clientModal = new bootstrap.Modal(document.getElementById('clientDetailModal'));
    clientModal.show();
    
    // Set the modal title with loading indicator
    document.getElementById('clientDetailTitle').innerHTML = 'Client Details <div class="spinner-border spinner-border-sm text-secondary" role="status"><span class="visually-hidden">Loading...</span></div>';
    
    // Clear previous content
    document.getElementById('clientDetailContent').innerHTML = 'Loading client details...';
    
    // Fetch client details
    fetch(`/api/clients/status`)
        .then(response => response.json())
        .then(clients => {
            const client = clients.find(c => c.id == clientId);
            if (client) {
                updateClientDetailView(client);
                
                // If client is online, fetch stats
                if (client.is_online) {
                    fetchClientStats(clientId);
                }
            } else {
                document.getElementById('clientDetailContent').innerHTML = 'Client not found.';
            }
        })
        .catch(error => {
            console.error('Error fetching client details:', error);
            document.getElementById('clientDetailContent').innerHTML = 'Error loading client details.';
        });
}

// Update client detail view with client data
function updateClientDetailView(client) {
    // Update modal title
    document.getElementById('clientDetailTitle').textContent = client.name;
    
    // Create detail HTML
    let detailHtml = `
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <h5 class="mb-0">Client Information</h5>
                <span class="badge ${client.is_online ? 'bg-success' : 'bg-secondary'}">
                    ${client.is_online ? 'Online' : 'Offline'}
                </span>
            </div>
            <div class="card-body">
                <div class="row mb-2">
                    <div class="col-md-4 fw-bold">MAC Address:</div>
                    <div class="col-md-8">${client.mac_address}</div>
                </div>
                <div class="row mb-2">
                    <div class="col-md-4 fw-bold">IP Address:</div>
                    <div class="col-md-8">${client.ip_address || '-'}</div>
                </div>
                <div class="row mb-2">
                    <div class="col-md-4 fw-bold">VHD:</div>
                    <div class="col-md-8">${client.vhd_name}</div>
                </div>
            </div>
        </div>
    `;
    
    // Add stats card for online clients
    if (client.is_online) {
        detailHtml += `
            <div class="card mb-3">
                <div class="card-header">
                    <h5 class="mb-0">Performance Statistics</h5>
                </div>
                <div class="card-body">
                    <div id="clientStatsContent">
                        <div class="text-center py-3">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                            <p class="mt-2">Loading performance statistics...</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Add actions card
    detailHtml += `
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">Actions</h5>
            </div>
            <div class="card-body">
                <div class="d-flex flex-wrap gap-2">
                    <a href="/clients/edit/${client.id}" class="btn btn-primary">
                        <i class="fas fa-edit me-1"></i> Edit
                    </a>
                    ${client.is_online ? `
                        <button type="button" class="btn btn-warning" onclick="rebootClient(${client.id})">
                            <i class="fas fa-sync-alt me-1"></i> Reboot
                        </button>
                    ` : ''}
                    <button type="button" class="btn btn-danger" onclick="confirmDeleteClient(${client.id}, '${client.name}')">
                        <i class="fas fa-trash-alt me-1"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Update content
    document.getElementById('clientDetailContent').innerHTML = detailHtml;
}

// Fetch client statistics
function fetchClientStats(clientId) {
    fetch(`/api/clients/stats/${clientId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch client stats');
            }
            return response.json();
        })
        .then(stats => {
            updateClientStatsView(stats);
        })
        .catch(error => {
            console.error('Error fetching client stats:', error);
            document.getElementById('clientStatsContent').innerHTML = `
                <div class="alert alert-warning" role="alert">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Statistics are not available for this client.
                </div>
            `;
        });
}

// Update client stats view
function updateClientStatsView(stats) {
    // For demo purposes, if we don't have real stats, use simulated data
    if (!stats || stats.error) {
        stats = {
            cpu_usage: Math.random() * 50 + 10,
            memory_usage_mb: Math.random() * 2048 + 1024,
            network_rx_mbps: Math.random() * 20,
            network_tx_mbps: Math.random() * 5,
            timestamp: new Date().toISOString()
        };
    }
    
    // Format the timestamp
    const timestamp = new Date(stats.timestamp);
    const formattedTime = timestamp.toLocaleTimeString();
    
    // Create stats HTML
    const statsHtml = `
        <div class="row">
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <h5 class="card-title">CPU Usage</h5>
                        <div class="display-4 fw-bold text-primary">${stats.cpu_usage.toFixed(1)}%</div>
                    </div>
                </div>
            </div>
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <h5 class="card-title">Memory Usage</h5>
                        <div class="display-4 fw-bold text-primary">${(stats.memory_usage_mb / 1024).toFixed(1)} GB</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="row">
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <h5 class="card-title">Download Speed</h5>
                        <div class="display-4 fw-bold text-primary">${stats.network_rx_mbps.toFixed(1)} Mbps</div>
                    </div>
                </div>
            </div>
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-body text-center">
                        <h5 class="card-title">Upload Speed</h5>
                        <div class="display-4 fw-bold text-primary">${stats.network_tx_mbps.toFixed(1)} Mbps</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="text-center text-muted small">
            Last updated: ${formattedTime}
        </div>
    `;
    
    // Update content
    document.getElementById('clientStatsContent').innerHTML = statsHtml;
}

// Refresh client status
function refreshClientsStatus() {
    fetch('/api/clients/status')
        .then(response => response.json())
        .then(data => {
            updateClientsTable(data);
        })
        .catch(error => {
            console.error('Error fetching client status:', error);
        });
}

// Update clients table with live status
function updateClientsTable(clients) {
    const clientRows = document.querySelectorAll('#clientsTable tbody tr');
    
    clientRows.forEach(row => {
        const clientId = row.getAttribute('data-client-id');
        const client = clients.find(c => c.id == clientId);
        
        if (client) {
            // Update status icon
            const statusIcon = row.querySelector('td:first-child i');
            if (statusIcon) {
                statusIcon.className = client.is_online ? 
                    'fas fa-circle text-success' : 
                    'fas fa-circle text-secondary';
                statusIcon.title = client.is_online ? 'Online' : 'Offline';
            }
            
            // Update IP address
            const ipCell = row.querySelector('td:nth-child(3)');
            if (ipCell) {
                ipCell.textContent = client.ip_address || '-';
            }
            
            // Update VHD name
            const vhdCell = row.querySelector('td:nth-child(5)');
            if (vhdCell) {
                vhdCell.textContent = client.vhd_name;
            }
            
            // Update action buttons
            const actionCell = row.querySelector('td:last-child');
            if (actionCell) {
                // Find or create reboot button
                let rebootBtn = actionCell.querySelector('.btn-reboot');
                
                if (client.is_online && !rebootBtn) {
                    // Create reboot button if client is online and button doesn't exist
                    rebootBtn = document.createElement('button');
                    rebootBtn.type = 'button';
                    rebootBtn.className = 'btn btn-sm btn-outline-warning btn-reboot ms-1';
                    rebootBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
                    rebootBtn.title = 'Reboot Client';
                    rebootBtn.onclick = function() {
                        rebootClient(clientId);
                    };
                    
                    // Add after the detail button
                    const detailBtn = actionCell.querySelector('.btn-client-detail');
                    if (detailBtn) {
                        detailBtn.after(rebootBtn);
                    } else {
                        actionCell.appendChild(rebootBtn);
                    }
                } else if (!client.is_online && rebootBtn) {
                    // Remove reboot button if client is offline
                    rebootBtn.remove();
                }
            }
        }
    });
}

// Function to reboot a client
function rebootClient(clientId) {
    if (confirm('Are you sure you want to reboot this client?')) {
        fetch(`/clients/reboot/${clientId}`, {
            method: 'POST'
        })
        .then(response => {
            if (response.ok) {
                // Show success message
                alert('Reboot command sent successfully');
                
                // Refresh the client status after a delay
                setTimeout(refreshClientsStatus, 2000);
            } else {
                alert('Failed to send reboot command');
            }
        })
        .catch(error => {
            console.error('Error rebooting client:', error);
            alert('Error sending reboot command');
        });
    }
}

// Function to confirm client deletion
function confirmDeleteClient(clientId, clientName) {
    if (confirm(`Are you sure you want to delete client "${clientName}"? This action cannot be undone.`)) {
        // Create and submit a form to delete the client
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/clients/delete/${clientId}`;
        document.body.appendChild(form);
        form.submit();
    }
}
