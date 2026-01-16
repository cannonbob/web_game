// Connect to socket.io
const socket = io();

// DOM elements
const questionText = document.getElementById('question-text');
const itemsContainer = document.getElementById('items-container');
const sortableList = document.getElementById('sortable-list');
const submitBtn = document.getElementById('submit-btn');
const statusMessage = document.getElementById('status-message');

// Game variables
let currentQuestion = null;
let items = [];
let hasSubmitted = false;
let draggedElement = null;

// Touch variables for mobile
let touchStartY = 0;
let touchCurrentY = 0;
let isDragging = false;
let touchedElement = null;
let placeholder = null;

// Socket event handlers
socket.on('connect', function() {
    console.log('Connected to Ordering Game');

    // Load question data from sessionStorage
    const storedData = sessionStorage.getItem('orderingQuestionData');
    if (storedData) {
        const data = JSON.parse(storedData);
        sessionStorage.removeItem('orderingQuestionData');
        console.log('Loaded question from sessionStorage:', data);
        handleQuestionData(data);
    } else {
        setStatus('Connected. Waiting for game to start...', 'info');
    }
});

// Handle reconnection - server sends forward_to_ordering_game with current question data
socket.on('forward_to_ordering_game', function(data) {
    console.log('Forwarded to ordering game (reconnection or initial):', data);
    handleQuestionData(data);
});

// Listen to question_selected event
socket.on('question_selected', function(data) {
    console.log('Question selected:', data);
    handleQuestionData(data);
});

// Listen for ordering game ready event
socket.on('ordering_game_ready', function(data) {
    console.log('Ordering game ready:', data);
    setStatus(data.message || 'Game ready!', 'info');
});

// Handle question data
function handleQuestionData(data) {
    currentQuestion = data.questionData;

    if (!currentQuestion || !currentQuestion.order_items || currentQuestion.order_items.length === 0) {
        setStatus('Error: No items to order', 'error');
        return;
    }

    // Show question
    questionText.textContent = data.question || currentQuestion.question_text || 'Order these items!';

    // Extract and shuffle items
    items = currentQuestion.order_items.map(item => item.item_name);
    shuffleArray(items);

    // Check if player has already submitted
    socket.emit('check_player_submitted', { question_id: currentQuestion.id });

    // Render items
    renderItems();

    // Show items container
    itemsContainer.style.display = 'block';
    resultsContainer.style.display = 'none';

    setStatus('Drag and drop to reorder the items!', 'info');
}

// Render sortable items
function renderItems() {
    sortableList.innerHTML = '';

    items.forEach((itemName, index) => {
        const li = document.createElement('li');
        li.className = 'sortable-item';
        li.draggable = true;
        li.dataset.index = index;
        li.dataset.itemName = itemName;

        li.innerHTML = `
            <div class="item-position">${index + 1}</div>
            <div class="item-name">${itemName}</div>
            <div class="drag-handle">☰</div>
        `;

        // Drag event listeners (for desktop)
        li.addEventListener('dragstart', handleDragStart);
        li.addEventListener('dragover', handleDragOver);
        li.addEventListener('drop', handleDrop);
        li.addEventListener('dragend', handleDragEnd);

        // Touch event listeners (for mobile)
        li.addEventListener('touchstart', handleTouchStart, { passive: false });
        li.addEventListener('touchmove', handleTouchMove, { passive: false });
        li.addEventListener('touchend', handleTouchEnd);

        sortableList.appendChild(li);
    });
}

// Drag and drop handlers
function handleDragStart(e) {
    draggedElement = this;
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';

    // Get the element we're dragging over
    const afterElement = getDragAfterElement(sortableList, e.clientY);

    if (afterElement == null) {
        sortableList.appendChild(draggedElement);
    } else {
        sortableList.insertBefore(draggedElement, afterElement);
    }

    return false;
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }

    // Update items array based on current DOM order
    updateItemsFromDOM();

    // Re-render to update position numbers
    renderItems();

    return false;
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
}

// Helper function to determine which element to insert before
function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.sortable-item:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;

        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// Helper function to update items array from current DOM order
function updateItemsFromDOM() {
    const allItems = sortableList.querySelectorAll('.sortable-item');
    items = Array.from(allItems).map(item => item.dataset.itemName);
}

// Touch event handlers for mobile
function handleTouchStart(e) {
    // Don't allow dragging if already submitted
    if (hasSubmitted) {
        return;
    }

    // Prevent default to stop scrolling when touching items
    e.preventDefault();

    touchedElement = this;
    touchStartY = e.touches[0].clientY;
    isDragging = false;

    // Add dragging class immediately for visual feedback
    this.classList.add('dragging');
}

function handleTouchMove(e) {
    // Don't allow dragging if already submitted
    if (hasSubmitted || !touchedElement) {
        return;
    }

    // Prevent default to stop scrolling
    e.preventDefault();

    isDragging = true;
    touchCurrentY = e.touches[0].clientY;

    // Move the element visually only - don't reorder DOM yet
    const deltaY = touchCurrentY - touchStartY;
    touchedElement.style.transform = `translateY(${deltaY}px)`;
    touchedElement.style.zIndex = '1000';

    // We'll reorder the DOM only on touchEnd to avoid position conflicts
}

function handleTouchEnd(e) {
    if (!touchedElement) return;

    // If we were dragging, reorder the DOM based on final position
    if (isDragging) {
        // Find which element we should be inserted before
        const afterElement = getTouchAfterElement(sortableList, touchCurrentY);

        // Reorder the DOM
        if (afterElement == null) {
            sortableList.appendChild(touchedElement);
        } else {
            sortableList.insertBefore(touchedElement, afterElement);
        }

        // Update items array based on new DOM order
        updateItemsFromDOM();

        // Re-render to update position numbers and reset styles
        renderItems();
    } else {
        // If it was just a tap without dragging, reset styles
        touchedElement.style.transform = '';
        touchedElement.style.zIndex = '';
        touchedElement.classList.remove('dragging');
    }

    // Reset touch variables
    touchedElement = null;
    isDragging = false;
    touchStartY = 0;
    touchCurrentY = 0;
}

// Helper function for touch dragging
function getTouchAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.sortable-item:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;

        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// Shuffle array helper
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

// Helper function to disable all dragging
function disableDragging() {
    const allItems = sortableList.querySelectorAll('.sortable-item');
    allItems.forEach(item => {
        item.draggable = false;
        item.style.cursor = 'default';
        item.style.touchAction = 'auto'; // Re-enable scrolling on items
    });
}

// Handle submit button click
submitBtn.addEventListener('click', function() {
    if (!currentQuestion || hasSubmitted) return;

    if (items.length === 0) {
        setStatus('No items to submit!', 'error');
        return;
    }

    // Submit order
    socket.emit('submit_order', {
        question_id: currentQuestion.id,
        order: items
    });

    hasSubmitted = true;
    submitBtn.disabled = true;

    // Disable dragging
    disableDragging();

    setStatus('Order submitted! Waiting for other players...', 'success');
});

// Player submission status
socket.on('player_submission_status', function(data) {
    console.log('Player submission status:', data);
    if (data.has_submitted) {
        hasSubmitted = true;
        submitBtn.disabled = true;

        // Disable dragging
        disableDragging();

        setStatus('You have already submitted your order!', 'success');
    }
});

// Order submitted confirmation
socket.on('order_submitted', function(data) {
    console.log('Order submitted:', data);
    if (data.success) {
        setStatus(data.message, 'success');
    }
});

// Submission update (for displaying count)
socket.on('submission_update', function(data) {
    console.log('Submission update:', data);
    if (hasSubmitted) {
        setStatus(`${data.count}/${data.total} players submitted. Waiting for others...`, 'info');
    }
});

// Ordering results - just disable controls, don't show results
socket.on('ordering_results', function(data) {
    console.log('Ordering results received - disabling controls');

    // Disable submit button
    submitBtn.disabled = true;

    // Disable all dragging
    disableDragging();

    // Clear status message
    setStatus('', '');
});

// Navigation listeners
socket.on('return_to_game_board', function() {
    window.location.href = '/waiting_room';
});

socket.on('admin_players_goto_waiting_room', function() {
    window.location.href = '/waiting_room';
});

socket.on('admin_players_goto_game_board', function() {
    window.location.href = '/waiting_room';
});

// Helper function to set status message
function setStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = 'status-message ' + type;
}
