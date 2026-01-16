// Main JavaScript for Game Platform

document.addEventListener('DOMContentLoaded', function() {
    // Helper Functions - These don't depend on Socket.IO
    
    /**
     * Show a notification message to the user
     * @param {string} message - The message to display
     * @param {string} type - The type of notification (success, error, info)
     * @param {number} duration - Duration in milliseconds to show the notification
     */
    window.showNotification = function(message, type = 'info', duration = 3000) {
        // Create notification element if it doesn't exist
        let notification = document.getElementById('notification');
        
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'notification';
            notification.className = 'notification';
            document.body.appendChild(notification);
            
            // Add styles
            notification.style.position = 'fixed';
            notification.style.top = '20px';
            notification.style.right = '20px';
            notification.style.padding = '10px 20px';
            notification.style.borderRadius = '5px';
            notification.style.color = 'white';
            notification.style.zIndex = '1000';
            notification.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
            notification.style.transition = 'opacity 0.3s, transform 0.3s';
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-20px)';
        }
        
        // Set type-specific styles
        if (type === 'success') {
            notification.style.backgroundColor = '#2ecc71';
        } else if (type === 'error' || type === 'danger') {
            notification.style.backgroundColor = '#e74c3c';
        } else {
            notification.style.backgroundColor = '#3498db';
        }
        
        // Set message and show notification
        notification.textContent = message;
        notification.style.opacity = '1';
        notification.style.transform = 'translateY(0)';
        
        // Hide notification after duration
        setTimeout(function() {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(-20px)';
        }, duration);
    };
});


// Helper Functions

/**
 * Show a notification message to the user
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, info)
 * @param {number} duration - Duration in milliseconds to show the notification
 */
function showNotification(message, type = 'info', duration = 3000) {
    // Create notification element if it doesn't exist
    let notification = document.getElementById('notification');
    
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        notification.className = 'notification';
        document.body.appendChild(notification);
        
        // Add styles
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.padding = '10px 20px';
        notification.style.borderRadius = '5px';
        notification.style.color = 'white';
        notification.style.zIndex = '1000';
        notification.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
        notification.style.transition = 'opacity 0.3s, transform 0.3s';
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-20px)';
    }
    
    // Set type-specific styles
    if (type === 'success') {
        notification.style.backgroundColor = '#2ecc71';
    } else if (type === 'error') {
        notification.style.backgroundColor = '#e74c3c';
    } else {
        notification.style.backgroundColor = '#3498db';
    }
    
    // Set message and show notification
    notification.textContent = message;
    notification.style.opacity = '1';
    notification.style.transform = 'translateY(0)';
    
    // Hide notification after duration
    setTimeout(function() {
        notification.style.opacity = '0';
        notification.style.transform = 'translateY(-20px)';
    }, duration);
}

/**
 * Create an animated countdown
 * @param {number} seconds - Number of seconds to count down from
 * @param {function} onComplete - Callback function when countdown completes
 * @param {string} containerId - ID of the container element for the countdown
 */
function createCountdown(seconds, onComplete, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Create countdown element
    const countdownEl = document.createElement('div');
    countdownEl.className = 'countdown';
    container.appendChild(countdownEl);
    
    // Start countdown
    let count = seconds;
    
    function updateCount() {
        countdownEl.textContent = count;
        
        if (count <= 0) {
            clearInterval(interval);
            container.removeChild(countdownEl);
            
            if (typeof onComplete === 'function') {
                onComplete();
            }
        }
        
        count--;
    }
    
    // Initial update
    updateCount();
    
    // Update every second
    const interval = setInterval(updateCount, 1000);
}

/**
 * Format time in seconds to MM:SS format
 * @param {number} seconds - Total seconds
 * @return {string} Formatted time string
 */
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
}

/**
 * Animate element transition with CSS classes
 * @param {HTMLElement} element - The element to animate
 * @param {string} animationClass - CSS class for the animation
 * @param {number} duration - Duration of the animation in milliseconds
 * @param {function} callback - Function to call after animation completes
 */
function animateElement(element, animationClass, duration, callback) {
    element.classList.add(animationClass);
    
    setTimeout(function() {
        element.classList.remove(animationClass);
        
        if (typeof callback === 'function') {
            callback();
        }
    }, duration);
}

/**
 * Fetch API helper with error handling
 * @param {string} url - The URL to fetch
 * @param {Object} options - Fetch options
 * @return {Promise} - Promise that resolves to the JSON response
 */
async function fetchData(url, options = {}) {
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        showNotification('Failed to load data. Please try again.', 'error');
        throw error;
    }
}
