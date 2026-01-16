// Match Me Game JavaScript

// Game state variables
let currentQuestion = null;
let correctAnswers = 0;
let incorrectAnswers = 0;
let questionsAnswered = 0;
let totalQuestions = 12;
let gameActive = false;
let currentPoints = 0;
let lastAnswerTime = 0; // Track when the last answer was selected

// DOM Elements
const gameContainer = document.getElementById('game-container');
const resultsContainer = document.getElementById('results-container');
const countdownContainer = document.getElementById('countdown-container');
const titleContainer = document.getElementById('title-container');
const artistsContainer = document.getElementById('artists-container');
const progressBar = document.getElementById('progress-bar');
const correctCount = document.getElementById('correct-count');
const incorrectCount = document.getElementById('incorrect-count');
const pointsDisplay = document.getElementById('points-display');
const finalPoints = document.getElementById('final-points');
const finalCorrect = document.getElementById('final-correct');
const finalTotal = document.getElementById('final-total');

// Connect to socket.io
const socket = io();

// Socket event handlers
socket.on('connect', function() {
    console.log('Connected to Match Me game');
    console.log('Socket ID:', socket.id);

    // Test socket connection by emitting a test event
    console.log('Sending test_socket event...');
    socket.emit('test_socket', { message: 'Match Me client connected' });
});

// Handle game_started event (for reconnection via Phase 2)
socket.on('game_started', function(data) {
    console.log('Game started event received (forwarding):', data);
    // Server will follow up with match_me_ready or match_me_reconnect
});

// Add general socket event listener to catch ANY event
socket.onAny((eventName, ...args) => {
    console.log(`Socket received event: ${eventName}`, args);
});

socket.on('test_response', function(data) {
    console.log('Received test_response:', data);
});

socket.on('forward_to_match_me', function(data) {
    console.log('Forwarded to match me:', data);
    if (typeof artistsContainer !== 'undefined' && artistsContainer) {
        artistsContainer.innerHTML = '<div class="alert alert-info">Waiting for game to start...</div>';
    }
    if (typeof gameContainer !== 'undefined' && gameContainer) gameContainer.classList.remove('d-none');
    if (typeof resultsContainer !== 'undefined' && resultsContainer) resultsContainer.classList.add('d-none');
});

socket.on('match_me_ready', function(data) {
    console.log('Match Me game is ready', data);
    if (typeof artistsContainer !== 'undefined' && artistsContainer) {
        artistsContainer.innerHTML = '<div class="alert alert-info">Waiting for game to start...</div>';
    }
    if (typeof gameContainer !== 'undefined' && gameContainer) gameContainer.classList.remove('d-none');
    if (typeof resultsContainer !== 'undefined' && resultsContainer) resultsContainer.classList.add('d-none');
});

// Handle reconnection to active game - player starts fresh
socket.on('match_me_reconnect', function() {
    console.log('Reconnecting to active Match Me game - starting fresh');

    // Reset local progress (player starts over - "bad luck")
    correctAnswers = 0;
    incorrectAnswers = 0;
    questionsAnswered = 0;
    currentPoints = 0;

    // Update UI
    updateProgress(0, totalQuestions, 0, 0);

    // Enable game immediately (skip countdown)
    gameContainer.classList.remove('d-none');
    resultsContainer.classList.add('d-none');
    countdownContainer.innerHTML = '';
    gameActive = true;

    // Show message
    titleContainer.innerHTML = '<div class="alert alert-info">Reconnected! Waiting for your first question...</div>';
    artistsContainer.innerHTML = '';

    console.log('Game active, waiting for match_me_question event');
});

socket.on('match_me_countdown', function(data) {
    console.log('Received match_me_countdown:', data);
    // Show countdown before game starts
    gameContainer.classList.add('d-none');
    resultsContainer.classList.add('d-none');
    
    createCountdown(data.countdown, function() {
        // Start game after countdown
        console.log('Countdown complete, showing game container');
        gameContainer.classList.remove('d-none');
        gameActive = true;
    }, 'countdown-container');
});

socket.on('match_me_question', function(data) {
    console.log('Received match_me_question:', data);

    // Animate out old question if there was one
    if (titleContainer.getAttribute('data-initialized') === 'true') {
        // Store the old question for comparison
        const oldQuestion = currentQuestion;

        // Calculate how long since the last answer was selected
        const timeSinceAnswer = Date.now() - lastAnswerTime;
        const feedbackDuration = 500; // Feedback animation is 500ms

        // If feedback animation is still playing, wait for it to finish
        if (timeSinceAnswer < feedbackDuration) {
            const remainingTime = feedbackDuration - timeSinceAnswer;
            console.log(`Waiting ${remainingTime}ms for feedback animation to complete`);

            setTimeout(() => {
                console.log('Animating question transition (after waiting)');
                animateQuestionTransition(oldQuestion, data);
                currentQuestion = data; // Update currentQuestion after animation starts
            }, remainingTime);
        } else {
            // Feedback animation is done, animate immediately
            console.log('Animating question transition (immediate)');
            animateQuestionTransition(oldQuestion, data);
            currentQuestion = data; // Update currentQuestion after animation starts
        }
    } else {
        // First question, just show it
        console.log('Rendering first question');
        currentQuestion = data;
        renderQuestion(data);
        titleContainer.setAttribute('data-initialized', 'true');
    }
});

socket.on('match_me_answer_result', function(data) {
    console.log('Debug - Received match_me_answer_result:', data);
    console.log('Debug - Progress data:', data.progress);
    console.log('Debug - Points change:', data.points_change);
    // Update progress
    updateProgress(data.progress.current, data.progress.total, data.progress.correct, data.progress.points);
});

socket.on('match_me_completed', function(data) {
    console.log('Debug - Received match_me_completed:', data);
    console.log('Debug - Correct answers from data:', data.correct_answers);
    console.log('Debug - Points from data:', data.points);
    console.log('Debug - Local correct answers:', correctAnswers);
    console.log('Debug - Local points:', currentPoints);
    console.log('Debug - Game ended early:', data.game_ended_early);
    
    // Game completed
    gameActive = false;
    gameContainer.classList.add('d-none');
    resultsContainer.classList.remove('d-none');
    
    // Use local values for final display
    finalPoints.textContent = currentPoints;
    finalCorrect.textContent = correctAnswers;
    finalTotal.textContent = questionsAnswered;
    console.log('Debug - Set final results - Points:', currentPoints, 'Correct:', correctAnswers, 'Total:', questionsAnswered);
});

socket.on('match_me_player_completed', function(data) {
    // Another player completed
    if (gameActive) {
        showNotification(`${data.username} has completed the game!`, 'info');
    }
});

socket.on('match_me_game_over', function(data) {
    // Game over for all players
    gameActive = false;

    // Log all scores for debugging
    console.log('Final game scores:', data.scores);
    console.log('Winner:', data.winner, 'with', data.winner_points, 'points');

    // Redirect to waiting room immediately
    window.location.href = '/waiting_room';
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

// Game functions
function renderQuestion(question) {
    // Set the title
    titleContainer.textContent = question.title;
    
    // Clear previous artists
    artistsContainer.innerHTML = '';
    
    // Add artists options
    question.artists.forEach(artist => {
        const artistElement = document.createElement('div');
        artistElement.className = 'artist-option';
        artistElement.textContent = artist.name;
        artistElement.dataset.id = artist.id;
        
        artistElement.addEventListener('click', function() {
            if (gameActive) {
                selectArtist(question.title_id, artist.id);
            }
        });
        
        artistsContainer.appendChild(artistElement);
    });
}

function selectArtist(titleId, artistId) {
    // Disable further selections
    gameActive = false;

    // Track when the answer was selected (for animation timing)
    lastAnswerTime = Date.now();

    console.log('Debug - Current question:', currentQuestion);
    console.log('Debug - Selected artist ID:', artistId);
    console.log('Debug - Correct artist ID:', currentQuestion.correct_artist_id);
    console.log('Debug - Artists array:', currentQuestion.artists);

    // Show which artist name was selected vs correct
    const selectedArtist = currentQuestion.artists.find(a => a.id == artistId);
    const correctArtist = currentQuestion.artists.find(a => a.id == currentQuestion.correct_artist_id);
    console.log('Debug - Selected artist name:', selectedArtist ? selectedArtist.name : 'NOT FOUND');
    console.log('Debug - Correct artist name:', correctArtist ? correctArtist.name : 'NOT FOUND');

    // Highlight selected option
    const selectedOption = document.querySelector(`.artist-option[data-id="${artistId}"]`);

    // Find correct option
    const correctId = currentQuestion.correct_artist_id;
    const correctOption = document.querySelector(`.artist-option[data-id="${correctId}"]`);

    // Check if answer is correct
    const isCorrect = artistId == correctId;
    console.log('Debug - Is correct?', isCorrect);

    if (isCorrect) {
        selectedOption.classList.add('correct');
        correctAnswers++;
        correctCount.textContent = correctAnswers;
        // Points will be updated by server response
    } else {
        selectedOption.classList.add('incorrect');
        correctOption.classList.add('correct');
        incorrectAnswers++;
        incorrectCount.textContent = incorrectAnswers;
        // Points deduction will be handled by server response
    }

    // Send answer to server
    socket.emit('match_me_answer', {
        title_id: titleId,
        artist_id: artistId
    });

    // Update local progress
    questionsAnswered++;
    updateProgressBar();
}

function updateProgressBar() {
    const percentage = (questionsAnswered / totalQuestions) * 100;
    progressBar.style.width = `${percentage}%`;
    progressBar.setAttribute('aria-valuenow', questionsAnswered);
    progressBar.textContent = `${questionsAnswered}/${totalQuestions}`;
}

function updateProgress(current, total, correct, points) {
    console.log('Debug - updateProgress called with:', {current, total, correct, points});
    console.log('Debug - Before update - correctAnswers:', correctAnswers, 'incorrectAnswers:', incorrectAnswers, 'currentPoints:', currentPoints);
    
    questionsAnswered = current;
    totalQuestions = total;
    // Don't override correctAnswers and incorrectAnswers - keep the local tracking
    // correctAnswers = correct;
    // incorrectAnswers = current - correct;
    
    // Update points from server (this handles the -5 deduction logic)
    if (points !== undefined) {
        currentPoints = points;
        pointsDisplay.textContent = currentPoints;
    }
    
    console.log('Debug - After update - correctAnswers:', correctAnswers, 'incorrectAnswers:', incorrectAnswers, 'currentPoints:', currentPoints);
    
    // Update UI with local values
    correctCount.textContent = correctAnswers;
    incorrectCount.textContent = incorrectAnswers;
    updateProgressBar();
    
    // Re-enable game after update
    gameActive = true;
}

function animateQuestionTransition(oldQuestion, newQuestion) {
    // Disable game during animation
    gameActive = false;

    // Animate title out
    titleContainer.classList.add('slide-out');

    // Get old artists for comparison
    const oldArtists = oldQuestion ? oldQuestion.artists : [];
    const artistElements = Array.from(document.querySelectorAll('.artist-option'));

    // Track which positions changed
    const changedPositions = [];

    // Compare old and new artists at each position
    newQuestion.artists.forEach((newArtist, index) => {
        const oldArtist = oldArtists[index];
        // Check if answer at this position changed
        if (!oldArtist || oldArtist.name !== newArtist.name) {
            changedPositions.push(index);
        }
    });

    console.log('Old artists:', oldArtists.map(a => a ? a.name : 'none'));
    console.log('New artists:', newQuestion.artists.map(a => a.name));
    console.log('Changed answer positions:', changedPositions);

    // Animate out only the changed answers
    artistElements.forEach((el, index) => {
        // Remove old styling first (correct/incorrect from feedback animation)
        el.classList.remove('correct', 'incorrect');

        if (changedPositions.includes(index)) {
            el.classList.add('slide-out');
        }
    });

    // After slide-out animation completes (500ms), update content and slide in
    setTimeout(() => {
        // Update title
        titleContainer.textContent = newQuestion.title;
        titleContainer.classList.remove('slide-out');
        titleContainer.classList.add('slide-in');

        // Update artist elements
        artistElements.forEach((el, index) => {
            const newArtist = newQuestion.artists[index];

            // Clone the element first (to remove old event listeners)
            const newEl = el.cloneNode(true);

            // Always update the ID (IDs change for all elements)
            newEl.dataset.id = newArtist.id;

            // Only update text and animate for changed positions
            if (changedPositions.includes(index)) {
                newEl.textContent = newArtist.name;
                newEl.classList.remove('slide-out');
                newEl.classList.add('slide-in');

                // Remove slide-in class after animation completes
                setTimeout(() => {
                    newEl.classList.remove('slide-in');
                }, 500);
            }

            // Add new click handler
            newEl.addEventListener('click', function() {
                if (gameActive) {
                    selectArtist(newQuestion.title_id, newArtist.id);
                }
            });

            // Replace the old element with the updated clone
            el.replaceWith(newEl);
        });

        // Remove animation classes from title and re-enable game
        setTimeout(() => {
            titleContainer.classList.remove('slide-in');
            gameActive = true;
        }, 500);
    }, 500);
}

// Helper function for countdown
function createCountdown(seconds, onComplete, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = '';
    
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
            container.innerHTML = '';
            
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
