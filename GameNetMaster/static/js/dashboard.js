// Dashboard JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize charts
    initializeStatusChart();
    initializeNetworkChart();

    // Refresh client status every 10 seconds
    refreshClientStatus();
    setInterval(refreshClientStatus, 10000);
});

// Initialize the client status donut chart
function initializeStatusChart() {
    const ctx = document.getElementById('clientStatusChart').getContext('2d');
    window.clientStatusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Online', 'Offline'],
            datasets: [{
                data: [0, 0],
                backgroundColor: [
                    'rgba(40, 167, 69, 0.8)',
                    'rgba(108, 117, 125, 0.8)'
                ],
                borderColor: [
                    'rgba(40, 167, 69, 1)',
                    'rgba(108, 117, 125, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            cutout: '70%'
        }
    });
}

// Initialize the network traffic chart
function initializeNetworkChart() {
    const ctx = document.getElementById('networkTrafficChart').getContext('2d');
    
    // Create 24 empty data points (for 24 hours)
    const labels = Array.from({length: 24}, (_, i) => i + ':00');
    const emptyData = Array(24).fill(0);
    
    window.networkTrafficChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Download (Mbps)',
                    data: emptyData,
                    borderColor: 'rgba(13, 110, 253, 1)',
                    backgroundColor: 'rgba(13, 110, 253, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Upload (Mbps)',
                    data: emptyData,
                    borderColor: 'rgba(220, 53, 69, 1)',
                    backgroundColor: 'rgba(220, 53, 69, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Mbps'
                    }
                }
            }
        }
    });
}

// Refresh client status
function refreshClientStatus() {
    fetch('/api/clients/status')
        .then(response => response.json())
        .then(data => {
            updateStatusChart(data);
            updateClientTable(data);
        })
        .catch(error => {
            console.error('Error fetching client status:', error);
        });
}

// Update the client status chart
function updateStatusChart(clients) {
    const online = clients.filter(client => client.is_online).length;
    const offline = clients.length - online;
    
    window.clientStatusChart.data.datasets[0].data = [online, offline];
    window.clientStatusChart.update();
    
    // Update the status counters
    document.getElementById('onlineCount').textContent = online;
    document.getElementById('totalCount').textContent = clients.length;
}

// Update the clients table
function updateClientTable(clients) {
    const tableBody = document.getElementById('clientsTableBody');
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    // Add new rows
    clients.forEach(client => {
        const row = document.createElement('tr');
        
        // Add status icon with appropriate color
        const statusCell = document.createElement('td');
        statusCell.className = 'text-center';
        const statusIcon = document.createElement('i');
        statusIcon.className = client.is_online ? 
            'fas fa-circle text-success' : 
            'fas fa-circle text-secondary';
        statusIcon.title = client.is_online ? 'Online' : 'Offline';
        statusCell.appendChild(statusIcon);
        row.appendChild(statusCell);
        
        // Add client name
        const nameCell = document.createElement('td');
        nameCell.textContent = client.name;
        row.appendChild(nameCell);
        
        // Add IP address
        const ipCell = document.createElement('td');
        ipCell.textContent = client.ip_address || '-';
        row.appendChild(ipCell);
        
        // Add MAC address
        const macCell = document.createElement('td');
        macCell.textContent = client.mac_address;
        row.appendChild(macCell);
        
        // Add VHD name
        const vhdCell = document.createElement('td');
        vhdCell.textContent = client.vhd_name;
        row.appendChild(vhdCell);
        
        // Add actions
        const actionCell = document.createElement('td');
        actionCell.className = 'text-end';
        
        // View details button
        const viewBtn = document.createElement('a');
        viewBtn.href = `/clients#client-${client.id}`;
        viewBtn.className = 'btn btn-sm btn-outline-primary me-1';
        viewBtn.innerHTML = '<i class="fas fa-eye"></i>';
        viewBtn.title = 'View Details';
        actionCell.appendChild(viewBtn);
        
        // Reboot button (only for online clients)
        if (client.is_online) {
            const rebootBtn = document.createElement('button');
            rebootBtn.type = 'button';
            rebootBtn.className = 'btn btn-sm btn-outline-warning';
            rebootBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
            rebootBtn.title = 'Reboot Client';
            rebootBtn.onclick = function() {
                if (confirm(`Are you sure you want to reboot ${client.name}?`)) {
                    rebootClient(client.id);
                }
            };
            actionCell.appendChild(rebootBtn);
        }
        
        row.appendChild(actionCell);
        
        // Add the row to the table
        tableBody.appendChild(row);
    });
}

// Function to reboot a client
function rebootClient(clientId) {
    fetch(`/clients/reboot/${clientId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => {
        if (response.ok) {
            // Refresh client status after reboot command
            setTimeout(refreshClientStatus, 2000);
        } else {
            console.error('Error rebooting client');
        }
    })
    .catch(error => {
        console.error('Error rebooting client:', error);
    });
}

// Function to update network chart with simulated data (for demo purposes)
function updateNetworkChart() {
    // In a real implementation, this would fetch actual network data
    // For the demo, we'll use simulated data
    
    // Generate random download/upload data
    const downloadData = Array.from({length: 24}, () => Math.random() * 50 + 10);
    const uploadData = Array.from({length: 24}, () => Math.random() * 20 + 5);
    
    window.networkTrafficChart.data.datasets[0].data = downloadData;
    window.networkTrafficChart.data.datasets[1].data = uploadData;
    window.networkTrafficChart.update();
}

// Update network chart with simulated data (for demo purposes)
setTimeout(updateNetworkChart, 1000);
