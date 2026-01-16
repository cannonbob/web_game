const socket = SocketManager.init();
const username = localStorage.getItem('username');

const ROWS = 5, COLS = 5, SEED = 777;
const img = new Image();
const scaledImg = document.createElement('canvas');
const scaledCtx = scaledImg.getContext('2d');

const canvas = document.getElementById('puzzleCanvas');
const ctx = canvas.getContext('2d');

let boardOffset = { x: 0, y: 0 };
let pieces = [], draggingPiece = null, dragOffset = { x: 0, y: 0 };
let pw, ph, tabSize;
let myTeam = null;
let gameActive = false;
let imageLoaded = false;

function seededRandom(s) {
    const x = Math.sin(s) * 10000;
    return x - Math.floor(x);
}

function loadImage(imagePath) {
    if (!imagePath) {
        console.error('No image path provided');
        return;
    }

    console.log('Loading image:', imagePath);
    img.src = imagePath;
}

img.onload = () => {
    // Get the actual available space from the wrapper element
    const wrapper = document.querySelector('.puzzle-canvas-wrapper');
    const wrapperRect = wrapper.getBoundingClientRect();
    const availableWidth = wrapperRect.width - 20; // Subtract padding
    const availableHeight = wrapperRect.height - 20; // Subtract padding

    // Use 90% of available width for the puzzle board
    const boardWidth = availableWidth * 0.9;

    // Calculate height based on image aspect ratio
    const aspectRatio = img.height / img.width;
    const scaledWidth = boardWidth;
    const scaledHeight = boardWidth * aspectRatio;

    // Calculate padding to center the puzzle and provide working space
    const paddingX = (availableWidth - scaledWidth) / 2;
    const paddingY = (availableHeight - scaledHeight) / 2;

    boardOffset = { x: paddingX, y: paddingY };

    // Create scaled version
    scaledImg.width = scaledWidth;
    scaledImg.height = scaledHeight;
    scaledCtx.drawImage(img, 0, 0, scaledWidth, scaledHeight);

    // Set canvas size to exactly fit in the wrapper (no CSS scaling needed)
    canvas.width = availableWidth;
    canvas.height = availableHeight;

    pw = scaledWidth / COLS;
    ph = scaledHeight / ROWS;
    tabSize = Math.min(pw, ph) * 0.28;

    initPuzzle();
    shufflePieces();
    draw();
    imageLoaded = true;
    console.log('Image loaded and scaled successfully');
};

function initPuzzle() {
    let s = SEED;
    const horiz = Array.from({length: ROWS}, () => []);
    const vert = Array.from({length: ROWS - 1}, () => []);

    for(let r=0; r<ROWS; r++)
        for(let c=0; c<COLS-1; c++) horiz[r][c] = seededRandom(s++) > 0.5 ? 1 : -1;
    for(let r=0; r<ROWS-1; r++)
        for(let c=0; c<COLS; c++) vert[r][c] = seededRandom(s++) > 0.5 ? 1 : -1;

    pieces = [];
    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            const pieceId = r * COLS + c;
            pieces.push({
                id: pieceId,
                sx: c*pw, sy: r*ph,
                tx: c*pw + boardOffset.x, ty: r*ph + boardOffset.y,
                x: 0, y: 0,
                isLocked: false,
                tabs: [
                    (r === 0) ? 0 : vert[r-1][c],
                    (c === COLS-1) ? 0 : horiz[r][c],
                    (r === ROWS - 1) ? 0 : vert[r][c],
                    (c === 0) ? 0 : horiz[r][c-1]
                ]
            });
        }
    }
}

function drawSide(ctx, x1, y1, x2, y2, type, invert) {
    if (type === 0) { ctx.lineTo(x2, y2); return; }
    const dx = x2 - x1, dy = y2 - y1;
    const dist = Math.sqrt(dx*dx + dy*dy);
    const nx = -dy / dist, ny = dx / dist;
    const actualType = invert ? -type : type;
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
    const cp1x = mx - (dx * 0.1), cp1y = my - (dy * 0.1);
    const cp2x = mx + (dx * 0.1), cp2y = my + (dy * 0.1);

    ctx.lineTo(cp1x, cp1y);
    ctx.bezierCurveTo(
        cp1x + nx * tabSize * actualType * 1.2, cp1y + ny * tabSize * actualType * 1.2,
        cp2x + nx * tabSize * actualType * 1.2, cp2y + ny * tabSize * actualType * 1.2,
        cp2x, cp2y
    );
    ctx.lineTo(x2, y2);
}

function definePath(ctx, p, x, y) {
    ctx.beginPath();
    ctx.moveTo(x, y);
    drawSide(ctx, x, y, x + pw, y, p.tabs[0], true);
    drawSide(ctx, x + pw, y, x + pw, y + ph, p.tabs[1], false);
    drawSide(ctx, x + pw, y + ph, x, y + ph, p.tabs[2], false);
    drawSide(ctx, x, y + ph, x, y, p.tabs[3], true);
    ctx.closePath();
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "#444";
    ctx.lineWidth = 5;
    ctx.setLineDash([10, 10]);
    ctx.strokeRect(boardOffset.x, boardOffset.y, scaledImg.width, scaledImg.height);
    ctx.setLineDash([]);

    ctx.globalAlpha = 0.05;
    ctx.drawImage(scaledImg, boardOffset.x, boardOffset.y);
    ctx.globalAlpha = 1.0;

    pieces.forEach(p => {
        ctx.save();
        definePath(ctx, p, p.x, p.y);
        ctx.clip();

        const b = tabSize + 2;
        ctx.drawImage(
            scaledImg,
            p.sx - b, p.sy - b, pw + b * 2, ph + b * 2,
            p.x - b, p.y - b, pw + b * 2, ph + b * 2
        );

        ctx.restore();

        ctx.strokeStyle = p.isLocked ? "rgba(0,255,0,0.6)" : "white";
        ctx.lineWidth = 1.5;
        definePath(ctx, p, p.x, p.y);
        ctx.stroke();
    });
}

function getPos(e) {
    const r = canvas.getBoundingClientRect();
    const sx = canvas.width / r.width, sy = canvas.height / r.height;
    const cx = e.touches ? e.touches[0].clientX : e.clientX;
    const cy = e.touches ? e.touches[0].clientY : e.clientY;
    return { x: (cx - r.left) * sx, y: (cy - r.top) * sy };
}

canvas.onpointerdown = (e) => {
    if (!gameActive) return;

    const pos = getPos(e);
    for (let i = pieces.length - 1; i >= 0; i--) {
        const p = pieces[i];
        if (!p.isLocked && pos.x > p.x && pos.x < p.x + pw && pos.y > p.y && pos.y < p.y + ph) {
            draggingPiece = p;
            dragOffset.x = pos.x - p.x;
            dragOffset.y = pos.y - p.y;
            pieces.push(pieces.splice(i, 1)[0]);
            break;
        }
    }
};

window.onpointermove = (e) => {
    if (!draggingPiece || !gameActive) return;
    const pos = getPos(e);
    draggingPiece.x = pos.x - dragOffset.x;
    draggingPiece.y = pos.y - dragOffset.y;
    draw();
};

window.onpointerup = () => {
    if (!draggingPiece || !gameActive) return;

    // Snap to target location
    if (Math.abs(draggingPiece.x - draggingPiece.tx) < 40 &&
        Math.abs(draggingPiece.y - draggingPiece.ty) < 40) {
        draggingPiece.x = draggingPiece.tx;
        draggingPiece.y = draggingPiece.ty;
        draggingPiece.isLocked = true;
    }

    // Send update to server
    socket.emit('coop_puzzle_update_piece', {
        piece_id: draggingPiece.id,
        x: draggingPiece.x,
        y: draggingPiece.y,
        isLocked: draggingPiece.isLocked
    });

    draggingPiece = null;
    draw();
};

function shufflePieces() {
    pieces.forEach(p => {
        p.isLocked = false;
        p.x = Math.random() * (canvas.width - pw);
        p.y = Math.random() * (canvas.height - ph);
    });
    draw();
}

// Socket.IO events
socket.on('connect', function() {
    console.log('Player connected, requesting game state');
    socket.emit('coop_puzzle_request_ready', {});
});

socket.on('coop_puzzle_ready', function(data) {
    console.log('Puzzle ready, teams:', data.teams);
    console.log('Image path:', data.image_path);

    // Load the puzzle image
    if (data.image_path && !imageLoaded) {
        loadImage(data.image_path);
    }

    // Find my team
    for (let [teamId, members] of Object.entries(data.teams)) {
        if (members.includes(username)) {
            myTeam = teamId;
            break;
        }
    }

});

socket.on('coop_puzzle_started', function(data) {
    console.log('Puzzle game started!');
    gameActive = true;
    shufflePieces();
});

socket.on('coop_puzzle_completed', function(data) {
    console.log('Puzzle completed by', data.winning_team);
    gameActive = false;

    const completionMsg = document.getElementById('completionMessage');
    const title = document.getElementById('completionTitle');
    const text = document.getElementById('completionText');

    if (data.winning_team === myTeam) {
        title.textContent = '🏆 VICTORY! 🏆';
        title.style.color = '#2ecc71';
        text.textContent = `Your team solved the puzzle! +1 point to: ${data.team_members.join(', ')}`;
    } else {
        title.textContent = 'Game Over';
        title.style.color = '#e74c3c';
        text.textContent = `${data.winning_team.toUpperCase()} won the game!`;
    }

    completionMsg.style.display = 'block';

    setTimeout(() => {
        completionMsg.style.display = 'none';
    }, 5000);
});

socket.on('game_ended', function() {
    gameActive = false;
});

socket.on('admin_players_goto_waiting_room', function() {
    window.location.href = '/waiting_room';
});
