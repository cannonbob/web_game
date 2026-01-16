// Flappy Birds Game JavaScript

// Game variables
let canvas, ctx;
let bird = {};
let pipes = [];
let score = 0;
let highScore = 0;
let gameActive = false;
let gameStarted = false;
let gameOver = false;
let gameInterval;
let pipeTimer;
let lastSubmittedScore = 0;

// Game constants
const GRAVITY = 0.5;
const FLAP_POWER = -8;
const PIPE_SPEED = 2;
const PIPE_SPAWN_INTERVAL = 1500;
const PIPE_GAP = 150;
const PIPE_WIDTH = 50;

// Fixed game loop timing
const GAME_TICK_RATE = 1000 / 60; // 16.67ms = 60 FPS


// Connect to socket.io
const socket = io();

// DOM elements
let gameStatus, currentScoreElement, highScoreElement, touchArea;

// Initialize game when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    gameStatus = document.getElementById('game-status');
    currentScoreElement = document.getElementById('current-score');
    highScoreElement = document.getElementById('high-score');
    touchArea = document.getElementById('touch-area');
    
    // Get canvas and context
    canvas = document.getElementById('game-canvas');
    ctx = canvas.getContext('2d');
    
    // Ensure canvas is properly set up
    if (canvas && ctx) {
        // Set initial game state
        resetGame();
        
        // Add event listeners
        document.addEventListener('keydown', function(e) {
            if (e.code === 'Space' && (gameActive || !gameStarted || gameOver)) {
                flap();
            }
        });
        
        if (touchArea) {
            touchArea.addEventListener('touchstart', function(e) {
                e.preventDefault();
                if (gameActive || !gameStarted || gameOver) {
                    flap();
                }
            });
            
            touchArea.addEventListener('mousedown', function() {
                if (gameActive || !gameStarted || gameOver) {
                    flap();
                }
            });
        }
        
        // Draw initial state - ensure canvas is properly rendered
        setTimeout(draw, 100);
    }
});

// Socket event handlers
socket.on('connect', function() {
    console.log('Connected to Flappy Birds game');

    // No specific action needed on connect
    // If game is active, server will send game_started event during reconnection
});

// Handle game_started event (for reconnection via Phase 2)
socket.on('game_started', function(data) {
    console.log('Game started event received (forwarding):', data);
    // Server will follow up with flappy_birds_started or flappy_birds_ready
});

socket.on('flappy_birds_ready', function() {
    console.log('Flappy Birds ready event received');
    gameStatus.textContent = 'Waiting for the admin to start the game...';
    gameStatus.className = 'alert alert-info';

    // Reset game
    resetGame();
    clearInterval(gameInterval);
    clearInterval(pipeTimer);
    draw();
});

socket.on('flappy_birds_started', function() {
    console.log('Flappy Birds started event received');
    gameStatus.textContent = 'Game started! Tap to flap.';
    gameStatus.className = 'alert alert-success';

    // Enable game but don't start until player taps
    gameActive = true;
    resetGame();
    draw(); // Redraw to show the ready state
});

// Handle score restoration on reconnection
socket.on('flappy_birds_restore_score', function(data) {
    console.log('Restoring high score:', data.high_score);
    highScore = data.high_score;
    if (highScoreElement) {
        highScoreElement.textContent = highScore;
    }
});

socket.on('flappy_birds_game_over', function(data) {
    // Game over for all players
    gameActive = false;
    clearInterval(gameInterval);
    clearInterval(pipeTimer);

    gameStatus.textContent = `Game Over! Winner: ${data.winner}`;
    gameStatus.className = 'alert alert-primary';

    // Draw final state
    draw();

    // Redirect to waiting room after delay
    setTimeout(function() {
        window.location.href = '/waiting_room';
    }, 5000);
});

socket.on('admin_players_goto_waiting_room', function() {
    // Admin clicked "Waiting Room" button - redirect immediately
    window.location.href = '/waiting_room';
});

// Game functions
function resetGame() {
    // Reset bird
    bird = {
        x: canvas.width / 4,
        y: canvas.height / 2,
        width: 30,
        height: 24,
        velocity: 0
    };
    
    // Reset pipes
    pipes = [];
    
    // Reset score
    score = 0;
    if (currentScoreElement) currentScoreElement.textContent = score;
    
    // Reset game state
    gameStarted = false;
    gameOver = false;
}

function startGame() {
    // Start game loop
    gameStarted = true;
    
    // Clear any existing interval
    clearInterval(gameInterval);
    
    // Start fixed-rate game loop
    gameInterval = setInterval(gameLoop, GAME_TICK_RATE);
    
    // Start pipe spawning
    clearInterval(pipeTimer);
    pipeTimer = setInterval(spawnPipe, PIPE_SPAWN_INTERVAL);
    
    // Spawn initial pipe
    spawnPipe();
}

function gameLoop() {
    if (!gameActive) {
        clearInterval(gameInterval);
        return;
    }
    
    // Update game state
    update();
    
    // Draw game
    draw();
}

function update() {
    // Apply gravity to bird
    bird.velocity += GRAVITY;
    bird.y += bird.velocity;
    
    // Check collision with ground
    if (bird.y + bird.height >= canvas.height) {
        handleGameOver();
        return;
    }
    
    // Check collision with ceiling
    if (bird.y <= 0) {
        bird.y = 0;
        bird.velocity = 0;
    }
    
    // Update pipes
    for (let i = 0; i < pipes.length; i++) {
        // Move pipe
        pipes[i].x -= PIPE_SPEED;
        
        // Check collision with bird
        if (checkCollision(bird, pipes[i])) {
            handleGameOver();
            return;
        }
        
        // Check if pipe is passed
        if (!pipes[i].passed && pipes[i].x + PIPE_WIDTH < bird.x) {
            pipes[i].passed = true;
            score++;
            currentScoreElement.textContent = score;
            
            // Update high score
            if (score > highScore) {
                highScore = score;
                highScoreElement.textContent = highScore;
            }
            
            // Submit score to server if increased by at least 5
            if (score - lastSubmittedScore >= 5) {
                submitScore(score);
                lastSubmittedScore = score;
            }
        }
    }
    
    // Remove off-screen pipes
    pipes = pipes.filter(pipe => pipe.x + PIPE_WIDTH > 0);
}

function draw() {
    // Debug canvas state
    if (!canvas || !ctx) {
        console.error('Canvas or context not available for drawing');
        return;
    }
    
    // Clear canvas
    ctx.fillStyle = '#87CEEB'; // Sky blue
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw ground
    ctx.fillStyle = '#8B4513'; // Brown
    ctx.fillRect(0, canvas.height - 20, canvas.width, 20);
    
    // Draw grass
    ctx.fillStyle = '#228B22'; // Forest green
    ctx.fillRect(0, canvas.height - 20, canvas.width, 5);
    
    // Draw pipes
    ctx.fillStyle = '#008000'; // Green
    for (let i = 0; i < pipes.length; i++) {
        const pipe = pipes[i];
        
        // Draw top pipe
        ctx.fillRect(pipe.x, 0, PIPE_WIDTH, pipe.topHeight);
        
        // Draw pipe cap
        ctx.fillStyle = '#006400'; // Dark green
        ctx.fillRect(pipe.x - 5, pipe.topHeight - 10, PIPE_WIDTH + 10, 10);
        ctx.fillStyle = '#008000'; // Green
        
        // Draw bottom pipe
        ctx.fillRect(pipe.x, pipe.topHeight + PIPE_GAP, PIPE_WIDTH, canvas.height - (pipe.topHeight + PIPE_GAP));
        
        // Draw pipe cap
        ctx.fillStyle = '#006400'; // Dark green
        ctx.fillRect(pipe.x - 5, pipe.topHeight + PIPE_GAP, PIPE_WIDTH + 10, 10);
        ctx.fillStyle = '#008000'; // Green
    }
    
    // Draw bird
    ctx.fillStyle = 'yellow';
    
    // Calculate bird rotation
    const rotation = bird.velocity * 0.1;
    
    // Save context state
    ctx.save();
    
    // Translate to bird center and rotate
    ctx.translate(bird.x + bird.width / 2, bird.y + bird.height / 2);
    ctx.rotate(rotation);
    
    // Draw bird body
    ctx.fillRect(-bird.width / 2, -bird.height / 2, bird.width, bird.height);
    
    // Draw bird wing
    ctx.fillStyle = 'orange';
    if (bird.velocity < 0) {
        // Wing up when flapping
        ctx.fillRect(-bird.width / 2, -bird.height / 2 - 5, bird.width - 10, 5);
    } else {
        // Wing down when falling
        ctx.fillRect(-bird.width / 2, bird.height / 2, bird.width - 10, 5);
    }
    
    // Draw bird eye
    ctx.fillStyle = 'white';
    ctx.beginPath();
    ctx.arc(bird.width / 4, -bird.height / 4, 5, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.fillStyle = 'black';
    ctx.beginPath();
    ctx.arc(bird.width / 4 + 2, -bird.height / 4, 2, 0, Math.PI * 2);
    ctx.fill();
    
    // Draw bird beak
    ctx.fillStyle = 'orange';
    ctx.beginPath();
    ctx.moveTo(bird.width / 2, 0);
    ctx.lineTo(bird.width / 2 + 10, -5);
    ctx.lineTo(bird.width / 2 + 10, 5);
    ctx.closePath();
    ctx.fill();
    
    // Restore context state
    ctx.restore();
    
    // Draw score
    ctx.fillStyle = 'white';
    ctx.font = '24px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(score, canvas.width / 2, 50);
    
    // Draw game over message
    if (gameOver) {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = 'white';
        ctx.font = '24px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('Game Over', canvas.width / 2, canvas.height / 2 - 20);
        ctx.fillText(`Score: ${score}`, canvas.width / 2, canvas.height / 2 + 20);
    }
}

function flap() {
    // If game is over, restart it
    if (gameOver) {
        gameActive = true;
        resetGame();
        startGame();
        return;
    }
    
    // If game hasn't started yet but is active, start it
    if (gameActive && !gameStarted) {
        startGame();
    }
    
    // Apply flap velocity if game is active
    if (gameActive) {
        bird.velocity = FLAP_POWER;
    }
}

function spawnPipe() {
    // Calculate random height for top pipe
    const minHeight = 50;
    const maxHeight = canvas.height - PIPE_GAP - 50;
    const topHeight = Math.floor(Math.random() * (maxHeight - minHeight + 1)) + minHeight;
    
    // Create new pipe
    const pipe = {
        x: canvas.width,
        topHeight: topHeight,
        passed: false
    };
    
    // Add pipe to array
    pipes.push(pipe);
}

function checkCollision(bird, pipe) {
    // Check collision with top pipe
    if (
        bird.x + bird.width > pipe.x &&
        bird.x < pipe.x + PIPE_WIDTH &&
        bird.y < pipe.topHeight
    ) {
        return true;
    }
    
    // Check collision with bottom pipe
    if (
        bird.x + bird.width > pipe.x &&
        bird.x < pipe.x + PIPE_WIDTH &&
        bird.y + bird.height > pipe.topHeight + PIPE_GAP
    ) {
        return true;
    }
    
    return false;
}

function handleGameOver() {
    gameActive = false;
    gameOver = true;
    
    // Stop the game loop
    clearInterval(gameInterval);
    
    // Submit final score
    submitScore(score);
    
    // Draw the game over screen
    draw();
}

function submitScore(score) {
    socket.emit('flappy_birds_submit_score', { score: score });
}
