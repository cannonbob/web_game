const TARGET = "JURASSIC PARK";
let currentChars = [];
const display = document.getElementById('movie-display');

function initDisplay() {
  display.innerHTML = '';
  currentChars = TARGET.split("");
  shuffleArray(currentChars);
  
  currentChars.forEach((char, i) => {
    const slot = document.createElement('div');
    slot.className = 'letter-slot';
    slot.id = `slot-${i}`;
    
    const letter = document.createElement('span');
    letter.className = 'letter-active';
    letter.id = `letter-${i}`;
    letter.innerText = char === " " ? "\u00A0" : char;
    
    slot.appendChild(letter);
    display.appendChild(slot);
  });
}

async function performSwap() {
  let wrongIndices = [];
  currentChars.forEach((char, i) => {
    if (char !== TARGET[i]) wrongIndices.push(i);
  });

  if (wrongIndices.length < 2) return;

  // Pick two random wrong indices
  const idxA = wrongIndices[Math.floor(Math.random() * wrongIndices.length)];
  let idxB = wrongIndices[Math.floor(Math.random() * wrongIndices.length)];
  while (idxA === idxB) idxB = wrongIndices[Math.floor(Math.random() * wrongIndices.length)];

  const letterA = document.getElementById(`letter-${idxA}`);
  const letterB = document.getElementById(`letter-${idxB}`);
  const slotA = document.getElementById(`slot-${idxA}`);
  const slotB = document.getElementById(`slot-${idxB}`);

  // Calculate distance
  const rectA = slotA.getBoundingClientRect();
  const rectB = slotB.getBoundingClientRect();
  const distance = rectB.left - rectA.left;

  // Animate: One goes up, one goes down
  letterA.style.transform = `translate(${distance}px, -60px)`;
  letterB.style.transform = `translate(${-distance}px, 60px)`;

  // Wait for animation, then reset positions and swap data
  setTimeout(() => {
    // Physically move them in the DOM to reset their "0" position
    letterA.style.transition = 'none';
    letterB.style.transition = 'none';
    letterA.style.transform = '';
    letterB.style.transform = '';
    
    slotA.appendChild(letterB);
    slotB.appendChild(letterA);
    
    // Update our logical tracking
    let temp = currentChars[idxA];
    currentChars[idxA] = currentChars[idxB];
    currentChars[idxB] = temp;
    
    // Sync IDs to match new slots
    letterA.id = `letter-${idxB}`;
    letterB.id = `letter-${idxA}`;
    
    // Re-enable transitions
    setTimeout(() => {
      letterA.style.transition = '';
      letterB.style.transition = '';
    }, 50);
  }, 1500);
}

function shuffleArray(array) {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
}

function resetGame() {
  initDisplay();
}

initDisplay();
setInterval(performSwap, 2500); // Trigger every 2.5s to allow for 1.5s animation