/**
 * Socket.IO utility functions
 * This file provides consistent Socket.IO initialization across pages
 */

// Define a global object for socket-related functionality
window.SocketManager = {
    // The socket instance
    socket: null,
    
    // Initialize socket with common handlers
    init: function() {
        // Only create the socket if it doesn't exist
        if (!this.socket) {
            console.log('Initializing Socket.IO connection');
            this.socket = io();
            
            // Set up basic handlers
            this.socket.on('connect', () => {
                console.log('Socket.IO connected!');
                this.updateStatus('success', 'Connected');
                
                if (typeof this.onConnected === 'function') {
                    this.onConnected();
                }
            });
            
            this.socket.on('disconnect', () => {
                console.log('Socket.IO disconnected');
                this.updateStatus('danger', 'Disconnected');
                
                if (typeof this.onDisconnected === 'function') {
                    this.onDisconnected();
                }
            });
            
            this.socket.on('connect_error', (err) => {
                console.error('Socket.IO connection error:', err);
                this.updateStatus('danger', 'Connection Error');
                
                if (typeof this.onConnectionError === 'function') {
                    this.onConnectionError(err);
                }
            });
        }
        
        return this.socket;
    },
    
    // Get the socket instance (initializing if needed)
    getSocket: function() {
        return this.socket || this.init();
    },
    
    // Add a status indicator to the page
    createStatusIndicator: function() {
        const indicator = document.createElement('div');
        indicator.id = 'socket-status-indicator';
        indicator.className = 'position-fixed bottom-0 end-0 p-3';
        indicator.innerHTML = `<span class="badge bg-secondary socket-status">Initializing...</span>`;
        document.body.appendChild(indicator);
        
        // Update status based on current socket state
        if (this.socket) {
            this.updateStatus(
                this.socket.connected ? 'success' : 'danger',
                this.socket.connected ? 'Connected' : 'Disconnected'
            );
        }
    },
    
    // Update the status indicator
    updateStatus: function(status, message) {
        let indicator = document.getElementById('socket-status-indicator');
        if (!indicator) {
            this.createStatusIndicator();
            indicator = document.getElementById('socket-status-indicator');
        }
        
        const statusBadge = indicator.querySelector('.socket-status');
        if (statusBadge) {
            statusBadge.className = `badge bg-${status} socket-status`;
            statusBadge.textContent = message;
        }
    },
    
    // Debug logging functionality
    debug: {
        panel: null,
        log: null,
        
        init: function() {
            if (!this.panel) {
                this.panel = document.createElement('div');
                this.panel.className = 'position-fixed bottom-0 start-0 p-3 bg-dark text-white small';
                this.panel.style.maxWidth = '300px';
                this.panel.style.opacity = '0.7';
                this.panel.innerHTML = '<h6>Debug Info</h6><div id="debug-log"></div>';
                document.body.appendChild(this.panel);
                this.log = document.getElementById('debug-log');
            }
            return this;
        },
        
        logMessage: function(message) {
            if (!this.log) this.init();
            
            console.log(message);
            const entry = document.createElement('div');
            entry.textContent = `${new Date().toLocaleTimeString()}: ${message}`;
            this.log.appendChild(entry);
            
            // Keep only the latest 10 messages
            while (this.log.children.length > 10) {
                this.log.removeChild(this.log.firstChild);
            }
        }
    }
};
