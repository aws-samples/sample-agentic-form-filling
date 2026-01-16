// AnyCompany Iframes - Check-in Application
// Challenges: Seat conflicts, iframes, ambiguous buttons, hidden elements

const BOOKING = {
  confirmation: "BW123",
  lastName: "Roe",
  passenger: { firstName: "Richard", lastName: "Roe" },
  flight: {
    number: "BW567",
    departure: { airport: "ATL", city: "Atlanta", date: "2025-02-01", time: "06:15", gate: "T4", terminal: "South" },
    arrival: { airport: "DFW", city: "Dallas" },
    aircraft: "AnyPlane 320E"
  },
  baggage: [
    { id: "cabin", name: "Cabin Bag", desc: "55x40x20cm, up to 10kg", price: 35 },
    { id: "checked", name: "Checked Bag", desc: "Up to 23kg", price: 45 },
    { id: "heavy", name: "Heavy Checked", desc: "Up to 32kg", price: 65 },
    { id: "priority", name: "Priority + Cabin", desc: "Board first + cabin bag", price: 42 }
  ],
  promos: [
    { id: "insurance", name: "Travel Insurance", price: 15 },
    { id: "seat-guarantee", name: "Seat Guarantee", price: 8 },
    { id: "flex", name: "Flexible Rebooking", price: 25 }
  ]
};

// State
const state = {
  validated: false,
  seat: null,
  seatOptions: { legroom: false, window: false },
  baggage: [],
  promos: [],
  termsRead: false,
  termsAgreed: false
};

function loadState() {
  const saved = sessionStorage.getItem('budgetwings-state');
  if (saved) {
    const allowedKeys = ['validated', 'seat', 'seatOptions', 'baggage', 'promos', 'termsRead', 'termsAgreed'];
    const parsed = JSON.parse(saved);
    const sanitizedData = Object.fromEntries(
      Object.entries(parsed).filter(([key]) => allowedKeys.includes(key))
    );
    Object.assign(state, sanitizedData);
  }
}

function saveState() {
  sessionStorage.setItem('budgetwings-state', JSON.stringify(state));
}

function clearState() {
  sessionStorage.removeItem('budgetwings-state');
  sessionStorage.removeItem('bw-seat');
  sessionStorage.removeItem('bw-occupied');
  sessionStorage.removeItem('bw-conflict');
}

// === LOGIN PAGE ===
// Ambiguous buttons - Look Up, Find, Continue all do slightly different things
function lookupBooking() {
  alert('Looking up your booking...\nPlease use the "Continue" button to proceed with check-in.');
}

function findBooking() {
  const ref = document.getElementById('ref').value.trim();
  if (ref) {
    alert(`Searching for booking ${ref}...\nPlease click "Continue" to check in.`);
  } else {
    alert('Please enter a booking reference first.');
  }
}

function handleLogin(event) {
  event.preventDefault();

  const ref = document.getElementById('ref').value.toUpperCase().trim();
  const surname = document.getElementById('surname').value.trim();

  const refErr = document.getElementById('ref-err');
  const surnameErr = document.getElementById('surname-err');

  document.getElementById('ref').classList.remove('error');
  document.getElementById('surname').classList.remove('error');
  refErr.textContent = '';
  surnameErr.textContent = '';

  let valid = true;

  if (ref !== BOOKING.confirmation) {
    document.getElementById('ref').classList.add('error');
    refErr.textContent = 'Booking not found';
    valid = false;
  }

  if (surname.toLowerCase() !== BOOKING.lastName.toLowerCase()) {
    document.getElementById('surname').classList.add('error');
    surnameErr.textContent = 'Surname does not match';
    valid = false;
  }

  if (valid) {
    clearState();
    state.validated = true;
    saveState();
    window.location.href = 'seats.html';
  }

  return false;
}

// === SEATS PAGE ===
function initSeats() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  document.getElementById('passenger-name').textContent =
    `${BOOKING.passenger.firstName} ${BOOKING.passenger.lastName}`;

  // Listen for messages from iframe
  window.addEventListener('message', handleIframeMessage);

  updateSeatDisplay();
}

function handleIframeMessage(event) {
  if (event.data.type === 'select') {
    state.seat = event.data.seat;
    sessionStorage.setItem('bw-seat', state.seat);
    saveState();
    updateSeatDisplay();

    // Show hidden options when seat selected
    if (state.seat) {
      document.getElementById('seat-options').style.display = 'block';
    }
  } else if (event.data.type === 'conflict') {
    showSeatConflict(event.data.seat);
  }
}

function updateSeatDisplay() {
  const display = document.getElementById('current-seat');
  const continueBtn = document.getElementById('continue-btn');

  if (state.seat) {
    display.textContent = `Selected: Seat ${state.seat}`;
    display.style.color = '#2196F3';
    display.style.fontWeight = 'bold';
    continueBtn.disabled = false;
  } else {
    display.textContent = 'No seat selected';
    display.style.color = '';
    display.style.fontWeight = '';
    continueBtn.disabled = true;
  }
}

function showSeatConflict(seatId) {
  state.seat = null;
  sessionStorage.removeItem('bw-seat');
  saveState();

  document.getElementById('conflict-seat').textContent = seatId;
  document.getElementById('conflict-banner').style.display = 'block';
  document.getElementById('seat-options').style.display = 'none';

  updateSeatDisplay();
}

function dismissConflict() {
  document.getElementById('conflict-banner').style.display = 'none';

  // Tell iframe to clear selection
  const iframe = document.getElementById('seat-iframe');
  iframe.contentWindow.postMessage({ action: 'clearSeat' }, window.location.origin);
}

// Ambiguous button actions
function selectRandomSeat() {
  alert('This would randomly select a seat for you.\nPlease use the seat map to choose your preferred seat.');
}

function autoAssign() {
  alert('Auto-assign will pick the best available seat at check-in.\nIf you want a specific seat, please select it from the map.');
}

function toggleOption(option) {
  state.seatOptions[option] = document.getElementById(
    option === 'legroom' ? 'extra-legroom' : 'window-guarantee'
  ).checked;
  saveState();
}

function handleContinue() {
  const page = document.body.dataset.page;

  switch (page) {
    case 'seats':
      window.location.href = 'bags.html';
      break;
    case 'bags':
      window.location.href = 'confirm.html';
      break;
  }
}

// === BAGS PAGE ===
function initBags() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderBagOptions();
  setupPromoReveal();
  startCountdown();
}

function renderBagOptions() {
  const container = document.getElementById('bag-options');
  if (!container) return;

  container.textContent = '';
  BOOKING.baggage.forEach(bag => {
    const isSelected = state.baggage.includes(bag.id);

    const label = document.createElement('label');
    label.className = 'bag-option' + (isSelected ? ' selected' : '');
    label.addEventListener('click', () => toggleBag(bag.id));

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = isSelected;

    const info = document.createElement('div');
    info.className = 'bag-info';
    const h4 = document.createElement('h4');
    h4.textContent = bag.name;
    const p = document.createElement('p');
    p.textContent = bag.desc;
    info.appendChild(h4);
    info.appendChild(p);

    const price = document.createElement('span');
    price.className = 'bag-price';
    price.textContent = '+$' + bag.price;

    label.appendChild(checkbox);
    label.appendChild(info);
    label.appendChild(price);
    container.appendChild(label);
  });
}

function toggleBag(bagId) {
  const idx = state.baggage.indexOf(bagId);
  if (idx === -1) {
    state.baggage.push(bagId);
  } else {
    state.baggage.splice(idx, 1);
  }
  saveState();
  renderBagOptions();
}

function setupPromoReveal() {
  const promoSection = document.getElementById('promo-section');

  // Reveal promo section after scrolling or after delay
  let revealed = false;

  const reveal = () => {
    if (revealed) return;
    revealed = true;
    promoSection.classList.add('visible');
    renderPromos();
  };

  // Reveal after 3 seconds or on scroll
  setTimeout(reveal, 3000);

  window.addEventListener('scroll', () => {
    if (window.scrollY > 100) reveal();
  });
}

function renderPromos() {
  const container = document.getElementById('promo-items');
  if (!container) return;

  container.textContent = '';
  BOOKING.promos.forEach(promo => {
    const label = document.createElement('label');
    label.className = 'promo-item';
    label.addEventListener('click', () => togglePromo(promo.id));

    const nameSpan = document.createElement('span');
    nameSpan.textContent = promo.name;

    const priceSpan = document.createElement('span');
    priceSpan.textContent = '+$' + promo.price;

    label.appendChild(nameSpan);
    label.appendChild(priceSpan);
    container.appendChild(label);
  });
}

function togglePromo(promoId) {
  const idx = state.promos.indexOf(promoId);
  if (idx === -1) {
    state.promos.push(promoId);
  } else {
    state.promos.splice(idx, 1);
  }
  saveState();
}

function startCountdown() {
  let seconds = 300; // 5 minutes
  const countdown = document.getElementById('countdown');

  const interval = setInterval(() => {
    seconds--;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    countdown.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;

    if (seconds <= 0) {
      clearInterval(interval);
      countdown.textContent = 'Expired';
    }
  }, 1000);
}

// Ambiguous buttons
function skipBags() {
  state.baggage = [];
  saveState();
  window.location.href = 'confirm.html';
}

function addRecommended() {
  // Add cabin bag if not selected
  if (!state.baggage.includes('cabin')) {
    state.baggage.push('cabin');
  }
  saveState();
  renderBagOptions();
  alert('Recommended baggage added: Cabin Bag');
}

// === CONFIRM PAGE ===
function initConfirm() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderSummary();
  setupTermsScroll();
}

function createSummaryRow(label, value) {
  const row = document.createElement('div');
  row.className = 'summary-row';
  const labelSpan = document.createElement('span');
  labelSpan.textContent = label;
  const valueSpan = document.createElement('span');
  valueSpan.textContent = value;
  row.appendChild(labelSpan);
  row.appendChild(valueSpan);
  return row;
}

function renderSummary() {
  const container = document.getElementById('summary');
  if (!container) return;

  container.textContent = '';
  const f = BOOKING.flight;
  let total = 0;

  container.appendChild(createSummaryRow('Flight', f.number + ': ' + f.departure.airport + ' → ' + f.arrival.airport));
  container.appendChild(createSummaryRow('Date/Time', f.departure.date + ' at ' + f.departure.time));
  container.appendChild(createSummaryRow('Passenger', BOOKING.passenger.firstName + ' ' + BOOKING.passenger.lastName));
  container.appendChild(createSummaryRow('Seat', state.seat || 'Not selected'));

  // Seat options
  if (state.seatOptions.legroom) {
    total += 25;
    container.appendChild(createSummaryRow('Extra Legroom', '+$25'));
  }
  if (state.seatOptions.window) {
    total += 10;
    container.appendChild(createSummaryRow('Window Guarantee', '+$10'));
  }

  // Baggage
  state.baggage.forEach(bagId => {
    const bag = BOOKING.baggage.find(b => b.id === bagId);
    if (bag) {
      total += bag.price;
      container.appendChild(createSummaryRow(bag.name, '+$' + bag.price));
    }
  });

  // Promos
  state.promos.forEach(promoId => {
    const promo = BOOKING.promos.find(p => p.id === promoId);
    if (promo) {
      total += promo.price;
      container.appendChild(createSummaryRow(promo.name, '+$' + promo.price));
    }
  });

  container.appendChild(createSummaryRow('Total Additional', '$' + total));
}

function setupTermsScroll() {
  const termsScroll = document.getElementById('terms-scroll');
  const checkbox = document.getElementById('terms-agree');
  const scrollHint = document.getElementById('scroll-hint');
  const confirmBtn = document.getElementById('confirm-btn');
  const completeBtn = document.getElementById('complete-btn');

  termsScroll.addEventListener('scroll', () => {
    const atBottom = termsScroll.scrollHeight - termsScroll.scrollTop <= termsScroll.clientHeight + 10;

    if (atBottom) {
      state.termsRead = true;
      checkbox.disabled = false;
      scrollHint.style.display = 'none';
    }
  });

  checkbox.addEventListener('change', () => {
    state.termsAgreed = checkbox.checked;
    confirmBtn.disabled = !state.termsAgreed;
    completeBtn.disabled = !state.termsAgreed;
  });
}

// Ambiguous buttons on confirm page
function saveForLater() {
  saveState();
  alert('Your progress has been saved.\nYou can return later to complete check-in using the same booking reference.');
}

function handleConfirm() {
  // First confirm button - shows confirmation
  if (confirm('Are you sure you want to complete check-in?')) {
    handleComplete();
  }
}

function handleComplete() {
  // Second confirm button - actually completes
  saveState();
  window.location.href = 'success.html';
}

// === SUCCESS PAGE ===
function initSuccess() {
  renderBoardingPass();
}

function renderBoardingPass() {
  const container = document.getElementById('boarding-pass');
  if (!container) return;

  container.textContent = '';
  const f = BOOKING.flight;
  const p = BOOKING.passenger;

  // Header
  const header = document.createElement('div');
  header.className = 'bp-header';
  const airline = document.createElement('span');
  airline.className = 'bp-airline';
  airline.textContent = 'AnyCompany Iframes';
  const passLabel = document.createElement('span');
  passLabel.textContent = 'Boarding Pass';
  header.appendChild(airline);
  header.appendChild(passLabel);

  // Route
  const route = document.createElement('div');
  route.className = 'bp-route';

  const depCity = document.createElement('div');
  depCity.className = 'bp-city';
  const depCode = document.createElement('div');
  depCode.className = 'bp-code';
  depCode.textContent = f.departure.airport;
  const depName = document.createElement('div');
  depName.className = 'bp-name';
  depName.textContent = f.departure.city;
  depCity.appendChild(depCode);
  depCity.appendChild(depName);

  const arrow = document.createElement('div');
  arrow.className = 'bp-arrow';
  arrow.textContent = '✈';

  const arrCity = document.createElement('div');
  arrCity.className = 'bp-city';
  const arrCode = document.createElement('div');
  arrCode.className = 'bp-code';
  arrCode.textContent = f.arrival.airport;
  const arrName = document.createElement('div');
  arrName.className = 'bp-name';
  arrName.textContent = f.arrival.city;
  arrCity.appendChild(arrCode);
  arrCity.appendChild(arrName);

  route.appendChild(depCity);
  route.appendChild(arrow);
  route.appendChild(arrCity);

  // Passenger
  const passenger = document.createElement('div');
  passenger.className = 'bp-passenger';
  passenger.textContent = p.firstName + ' ' + p.lastName;

  // Details
  const details = document.createElement('div');
  details.className = 'bp-details';

  const detailItems = [
    { label: 'Date', value: f.departure.date },
    { label: 'Time', value: f.departure.time },
    { label: 'Gate', value: f.departure.gate },
    { label: 'Seat', value: state.seat || 'TBA' }
  ];

  detailItems.forEach(item => {
    const div = document.createElement('div');
    const labelDiv = document.createElement('div');
    labelDiv.className = 'bp-label';
    labelDiv.textContent = item.label;
    const valueDiv = document.createElement('div');
    valueDiv.className = 'bp-value';
    valueDiv.textContent = item.value;
    div.appendChild(labelDiv);
    div.appendChild(valueDiv);
    details.appendChild(div);
  });

  container.appendChild(header);
  container.appendChild(route);
  container.appendChild(passenger);
  container.appendChild(details);
}

function downloadPass() {
  const f = BOOKING.flight;
  const p = BOOKING.passenger;

  const content = `BUDGETWINGS - BOARDING PASS
${'='.repeat(40)}
Confirmation: ${BOOKING.confirmation}
Flight: ${f.number}
Route: ${f.departure.airport} (${f.departure.city}) → ${f.arrival.airport} (${f.arrival.city})
Date: ${f.departure.date}
${'='.repeat(40)}

PASSENGER: ${p.firstName} ${p.lastName}
Seat: ${state.seat || 'To be assigned'}
Terminal: ${f.departure.terminal}
Gate: ${f.departure.gate}
Boarding: ${f.departure.time}

${'='.repeat(40)}
*** ARRIVE AT GATE 30 MINUTES BEFORE DEPARTURE ***
*** PERSONAL ITEM ONLY - BAGGAGE FEES APPLY ***
`;

  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `boarding-pass-${BOOKING.confirmation}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function emailPass() {
  alert('Boarding pass will be sent to the email address on file.');
}

function newCheckIn() {
  clearState();
  window.location.href = 'index.html';
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
  loadState();

  const page = document.body.dataset.page;
  switch (page) {
    case 'seats': initSeats(); break;
    case 'bags': initBags(); break;
    case 'confirm': initConfirm(); break;
    case 'success': initSuccess(); break;
  }
});
