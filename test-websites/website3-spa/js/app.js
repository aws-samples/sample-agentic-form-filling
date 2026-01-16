// AnyCompany SPA - Modern SPA Check-in Application

const BOOKING = {
  confirmation: "AJ2024",
  lastName: "Santos",
  flight: {
    number: "AJ890",
    airline: "AnyCompany SPA",
    departure: { airport: "SEA", city: "Seattle", date: "2025-01-25", time: "10:30", gate: "A15", terminal: "N" },
    arrival: { airport: "DEN", city: "Denver", date: "2025-01-25", time: "14:15" },
    aircraft: "AnyPlane 700X",
    duration: "2h 45m"
  },
  passengers: [
    { id: 1, firstName: "Paulo", lastName: "Santos" },
    { id: 2, firstName: "Saanvi", lastName: "Santos" }
  ],
  seatMap: {
    rows: 28,
    columns: ["A", "B", "C", "D", "E", "F"],
    premiumRows: [1, 2, 3, 4],
    exitRows: [12, 13],
    premiumPrice: 35
  },
  baggage: [
    { id: "cabin", name: "Extra Cabin Bag", price: 25, desc: "Additional carry-on" },
    { id: "checked", name: "Extra Checked Bag", price: 35, desc: "Up to 23kg" },
    { id: "heavy", name: "Overweight Allowance", price: 55, desc: "23-32kg per bag" }
  ],
  extras: [
    { id: "insurance", name: "Travel Insurance", price: 19, desc: "Trip protection coverage" },
    { id: "wifi", name: "In-flight WiFi", price: 9, desc: "High-speed streaming" },
    { id: "meal", name: "Premium Meal Box", price: 14, desc: "Chef-curated selection" },
    { id: "lounge", name: "Lounge Pass", price: 39, desc: "Pre-flight relaxation" }
  ]
};

// Application State
const state = {
  currentStep: 0,
  validated: false,
  currentPassenger: 0,
  seats: {},
  baggage: { 1: [], 2: [] },
  extras: [],
  occupiedSeats: [],
  dynamicUnavailable: []
};

const STEPS = ['login', 'seats', 'baggage', 'extras', 'review', 'success'];

// XSS Protection: Escape HTML special characters
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// Utility functions
function loadState() {
  const saved = sessionStorage.getItem('aerojet-state');
  if (saved) {
    const parsed = JSON.parse(saved);
    // Whitelist allowed state properties to prevent mass assignment vulnerabilities
    const allowedKeys = ['currentStep', 'validated', 'currentPassenger', 'seats', 'baggage', 'extras', 'occupiedSeats', 'dynamicUnavailable'];
    const sanitizedData = Object.fromEntries(
      Object.entries(parsed).filter(([key]) => allowedKeys.includes(key))
    );
    Object.assign(state, sanitizedData);
  }
}

function saveState() {
  sessionStorage.setItem('aerojet-state', JSON.stringify(state));
}

function clearState() {
  sessionStorage.removeItem('aerojet-state');
}

// Generate initial occupied seats
function generateOccupiedSeats() {
  const occupied = [];
  const { rows, columns } = BOOKING.seatMap;
  for (let row = 1; row <= rows; row++) {
    for (const col of columns) {
      if (Math.random() < 0.3) {
        occupied.push(`${row}${col}`);
      }
    }
  }
  return occupied;
}

// UI Helpers
function showSpinner(text = "Loading...") {
  const overlay = document.getElementById('spinner-overlay');
  const spinnerText = document.getElementById('spinner-text');
  if (spinnerText) spinnerText.textContent = text;
  if (overlay) overlay.classList.add('active');
}

function hideSpinner() {
  const overlay = document.getElementById('spinner-overlay');
  if (overlay) overlay.classList.remove('active');
}

function showModal(title, body, onConfirm) {
  const overlay = document.getElementById('modal-overlay');
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').textContent = body;
  document.getElementById('modal-confirm').onclick = () => {
    overlay.classList.remove('active');
    if (onConfirm) onConfirm();
  };
  document.getElementById('modal-cancel').onclick = () => {
    overlay.classList.remove('active');
  };
  overlay.classList.add('active');
}

function updateProgress() {
  const stepIndex = STEPS.indexOf(state.currentStep);
  const percent = (stepIndex / (STEPS.length - 1)) * 100;

  const fill = document.getElementById('progress-fill');
  if (fill) fill.style.width = `${percent}%`;

  document.querySelectorAll('.progress-step').forEach((el, idx) => {
    el.classList.remove('active', 'completed');
    if (idx < stepIndex) el.classList.add('completed');
    if (idx === stepIndex) el.classList.add('active');
  });
}

function showStep(step) {
  state.currentStep = step;
  saveState();
  updateProgress();

  document.querySelectorAll('.step-section').forEach(el => {
    el.classList.remove('active');
  });

  const section = document.getElementById(`step-${step}`);
  if (section) section.classList.add('active');
}

// Login
function validateLogin(event) {
  event.preventDefault();

  const code = document.getElementById('code').value.toUpperCase().trim();
  const name = document.getElementById('name').value.trim();

  const codeInput = document.getElementById('code');
  const nameInput = document.getElementById('name');
  const codeError = document.getElementById('code-error');
  const nameError = document.getElementById('name-error');

  codeInput.classList.remove('error');
  nameInput.classList.remove('error');
  codeError.textContent = '';
  nameError.textContent = '';

  let valid = true;

  if (code !== BOOKING.confirmation) {
    codeInput.classList.add('error');
    codeError.textContent = 'Invalid confirmation code';
    valid = false;
  }

  if (name.toLowerCase() !== BOOKING.lastName.toLowerCase()) {
    nameInput.classList.add('error');
    nameError.textContent = 'Last name does not match booking';
    valid = false;
  }

  if (valid) {
    showSpinner("Finding your booking...");
    setTimeout(() => {
      clearState();
      state.validated = true;
      state.occupiedSeats = generateOccupiedSeats();
      saveState();
      hideSpinner();
      goToSeats();
    }, 1500);
  }

  return false;
}

// Seats
function goToSeats() {
  showStep('seats');
  showSpinner("Loading seat map...");

  // Simulate API delay
  setTimeout(() => {
    hideSpinner();
    renderSeatMap();
    renderPassengerPanel();
    updateSeatContinueButton();

    // Simulate dynamic unavailability after 3 seconds
    setTimeout(makeSomeSeatsUnavailable, 3000);
  }, 2000);
}

function makeSomeSeatsUnavailable() {
  const { rows, columns } = BOOKING.seatMap;
  const available = [];

  for (let row = 1; row <= rows; row++) {
    for (const col of columns) {
      const seatId = `${row}${col}`;
      if (!state.occupiedSeats.includes(seatId) &&
          !Object.values(state.seats).includes(seatId)) {
        available.push(seatId);
      }
    }
  }

  // Make 5 random seats unavailable
  const toRemove = available.sort(() => Math.random() - 0.5).slice(0, 5);
  state.dynamicUnavailable = toRemove;

  toRemove.forEach(seatId => {
    const btn = document.querySelector(`[data-seat="${seatId}"]`);
    if (btn && !btn.classList.contains('selected')) {
      btn.classList.add('becoming-unavailable');
      setTimeout(() => {
        btn.classList.remove('becoming-unavailable');
        btn.classList.add('occupied');
        btn.disabled = true;
        state.occupiedSeats.push(seatId);
      }, 1000);
    }
  });

  saveState();
}

function renderSeatMap() {
  const container = document.getElementById('seat-map-content');
  if (!container) return;

  const { rows, columns, premiumRows, exitRows } = BOOKING.seatMap;
  const selectedSeats = Object.values(state.seats);
  const currentPassengerId = BOOKING.passengers[state.currentPassenger].id;
  const currentSeat = state.seats[currentPassengerId];

  container.textContent = '';

  // Aircraft header
  const aircraftHeader = document.createElement('div');
  aircraftHeader.className = 'aircraft-header';

  const aircraftNose = document.createElement('div');
  aircraftNose.className = 'aircraft-nose';
  aircraftHeader.appendChild(aircraftNose);

  const frontLabel = document.createElement('div');
  frontLabel.style.cssText = 'font-size: 0.875rem; color: var(--gray-500); margin-top: 0.5rem;';
  frontLabel.textContent = 'Front of Aircraft';
  aircraftHeader.appendChild(frontLabel);

  container.appendChild(aircraftHeader);

  // Column labels
  const colLabels = document.createElement('div');
  colLabels.className = 'col-labels';

  columns.forEach((col, idx) => {
    const colLabel = document.createElement('span');
    colLabel.className = 'col-label';
    colLabel.textContent = col;
    colLabels.appendChild(colLabel);

    if (idx === 2) {
      const aisle = document.createElement('span');
      aisle.className = 'aisle';
      colLabels.appendChild(aisle);
    }
  });

  container.appendChild(colLabels);

  // Seat grid
  const seatGrid = document.createElement('div');
  seatGrid.className = 'seat-grid';

  for (let row = 1; row <= rows; row++) {
    const seatRow = document.createElement('div');
    seatRow.className = 'seat-row';

    const rowLabel = document.createElement('span');
    rowLabel.className = 'row-label';
    rowLabel.textContent = row;
    seatRow.appendChild(rowLabel);

    columns.forEach((col, idx) => {
      const seatId = row + col;
      const isOccupied = state.occupiedSeats.includes(seatId);
      const isSelectedByOther = selectedSeats.includes(seatId) && state.seats[currentPassengerId] !== seatId;
      const isCurrentSeat = currentSeat === seatId;

      const classes = ['seat'];
      if (isOccupied || isSelectedByOther) {
        classes.push('occupied');
      } else if (isCurrentSeat) {
        classes.push('selected');
      }

      const clickable = !isOccupied && !isSelectedByOther;

      const button = document.createElement('button');
      button.className = classes.join(' ');
      button.dataset.seat = seatId;
      button.setAttribute('aria-label', 'Seat ' + seatId);
      button.textContent = col;

      if (clickable) {
        button.onclick = () => selectSeat(seatId);
      } else {
        button.disabled = true;
      }

      seatRow.appendChild(button);

      if (idx === 2) {
        const aisle = document.createElement('span');
        aisle.className = 'aisle';
        seatRow.appendChild(aisle);
      }
    });

    seatGrid.appendChild(seatRow);
  }

  container.appendChild(seatGrid);

  // Seat legend
  const seatLegend = document.createElement('div');
  seatLegend.className = 'seat-legend';

  const legendItems = [
    { color: 'var(--gray-200)', label: 'Available' },
    { color: 'var(--primary)', label: 'Selected' },
    { color: 'var(--gray-400)', label: 'Unavailable' }
  ];

  legendItems.forEach(item => {
    const legendItem = document.createElement('div');
    legendItem.className = 'legend-item';

    const legendDot = document.createElement('div');
    legendDot.className = 'legend-dot';
    legendDot.style.background = item.color;
    legendItem.appendChild(legendDot);

    const legendLabel = document.createElement('span');
    legendLabel.textContent = item.label;
    legendItem.appendChild(legendLabel);

    seatLegend.appendChild(legendItem);
  });

  container.appendChild(seatLegend);
}

function renderPassengerPanel() {
  const container = document.getElementById('passenger-panel');
  if (!container) return;

  container.textContent = '';
  BOOKING.passengers.forEach((p, idx) => {
    const seat = state.seats[p.id];
    const isActive = idx === state.currentPassenger;
    const hasSeat = seat !== null && seat !== undefined;

    const card = document.createElement('div');
    card.className = 'passenger-card' + (isActive ? ' active' : '') + (hasSeat ? ' has-seat' : '');
    card.onclick = () => selectPassenger(idx);

    const nameDiv = document.createElement('div');
    nameDiv.className = 'passenger-name';
    nameDiv.textContent = p.firstName + ' ' + p.lastName;
    card.appendChild(nameDiv);

    const seatDiv = document.createElement('div');
    seatDiv.className = 'passenger-seat';
    seatDiv.textContent = hasSeat ? 'Seat ' + seat : 'Click to select seat';
    card.appendChild(seatDiv);

    container.appendChild(card);
  });
}

function selectPassenger(idx) {
  state.currentPassenger = idx;
  saveState();
  renderPassengerPanel();
  renderSeatMap();
}

function selectSeat(seatId) {
  const currentPassengerId = BOOKING.passengers[state.currentPassenger].id;

  showModal(
    'Confirm Seat Selection',
    `Select seat ${seatId} for ${BOOKING.passengers[state.currentPassenger].firstName}?`,
    () => {
      if (state.seats[currentPassengerId] === seatId) {
        delete state.seats[currentPassengerId];
      } else {
        state.seats[currentPassengerId] = seatId;
      }
      saveState();
      renderPassengerPanel();
      renderSeatMap();
      updateSeatContinueButton();
    }
  );
}

function updateSeatContinueButton() {
  const btn = document.getElementById('seats-continue');
  if (btn) {
    const allSelected = BOOKING.passengers.every(p => state.seats[p.id]);
    btn.disabled = !allSelected;
  }
}

// Baggage
function goToBaggage() {
  showStep('baggage');
  showSpinner("Loading baggage options...");

  setTimeout(() => {
    hideSpinner();
    renderBaggageOptions();
  }, 1000);
}

function renderBaggageOptions() {
  const container = document.getElementById('baggage-content');
  if (!container) return;

  container.textContent = '';
  BOOKING.passengers.forEach(p => {
    const card = document.createElement('div');
    card.className = 'card';

    const h3 = document.createElement('h3');
    h3.style.marginBottom = '1rem';
    h3.textContent = p.firstName + ' ' + p.lastName;
    card.appendChild(h3);

    const includedP = document.createElement('p');
    includedP.style.cssText = 'color: var(--gray-500); margin-bottom: 1rem; font-size: 0.875rem;';
    includedP.textContent = 'Included: 1 cabin bag (8kg), 1 checked bag (23kg)';
    card.appendChild(includedP);

    const optionsGrid = document.createElement('div');
    optionsGrid.className = 'options-grid';

    BOOKING.baggage.forEach(opt => {
      const isSelected = state.baggage[p.id]?.includes(opt.id);

      const label = document.createElement('label');
      label.className = 'option-card' + (isSelected ? ' selected' : '');

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'option-checkbox';
      checkbox.checked = isSelected;
      checkbox.onchange = () => toggleBaggage(p.id, opt.id);
      label.appendChild(checkbox);

      const optionInfo = document.createElement('div');
      optionInfo.className = 'option-info';

      const optionName = document.createElement('div');
      optionName.className = 'option-name';
      optionName.textContent = opt.name;
      optionInfo.appendChild(optionName);

      const optionDesc = document.createElement('div');
      optionDesc.className = 'option-desc';
      optionDesc.textContent = opt.desc;
      optionInfo.appendChild(optionDesc);

      label.appendChild(optionInfo);

      const optionPrice = document.createElement('div');
      optionPrice.className = 'option-price';
      optionPrice.textContent = '+$' + opt.price;
      label.appendChild(optionPrice);

      optionsGrid.appendChild(label);
    });

    card.appendChild(optionsGrid);
    container.appendChild(card);
  });
}

function toggleBaggage(passengerId, optionId) {
  if (!state.baggage[passengerId]) state.baggage[passengerId] = [];

  const idx = state.baggage[passengerId].indexOf(optionId);
  if (idx === -1) {
    state.baggage[passengerId].push(optionId);
  } else {
    state.baggage[passengerId].splice(idx, 1);
  }

  saveState();
  renderBaggageOptions();
}

// Extras
function goToExtras() {
  showStep('extras');
  renderExtrasOptions();
}

function renderExtrasOptions() {
  const container = document.getElementById('extras-content');
  if (!container) return;

  container.textContent = '';

  const optionsGrid = document.createElement('div');
  optionsGrid.className = 'options-grid';

  BOOKING.extras.forEach(opt => {
    const isSelected = state.extras.includes(opt.id);

    const label = document.createElement('label');
    label.className = 'option-card' + (isSelected ? ' selected' : '');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'option-checkbox';
    checkbox.checked = isSelected;
    checkbox.onchange = () => toggleExtra(opt.id);
    label.appendChild(checkbox);

    const optionInfo = document.createElement('div');
    optionInfo.className = 'option-info';

    const optionName = document.createElement('div');
    optionName.className = 'option-name';
    optionName.textContent = opt.name;
    optionInfo.appendChild(optionName);

    const optionDesc = document.createElement('div');
    optionDesc.className = 'option-desc';
    optionDesc.textContent = opt.desc;
    optionInfo.appendChild(optionDesc);

    label.appendChild(optionInfo);

    const optionPrice = document.createElement('div');
    optionPrice.className = 'option-price';
    optionPrice.textContent = '+$' + opt.price;
    label.appendChild(optionPrice);

    optionsGrid.appendChild(label);
  });

  container.appendChild(optionsGrid);
}

function toggleExtra(optionId) {
  const idx = state.extras.indexOf(optionId);
  if (idx === -1) {
    state.extras.push(optionId);
  } else {
    state.extras.splice(idx, 1);
  }
  saveState();
  renderExtrasOptions();
}

// Review
function goToReview() {
  showStep('review');
  renderReview();
}

// Helper function to create review row elements
function createReviewRow(labelText, valueText) {
  const row = document.createElement('div');
  row.className = 'review-row';

  const label = document.createElement('span');
  label.className = 'review-label';
  label.textContent = labelText;
  row.appendChild(label);

  const value = document.createElement('span');
  value.className = 'review-value';
  value.textContent = valueText;
  row.appendChild(value);

  return row;
}

function renderReview() {
  const f = BOOKING.flight;

  // Flight
  const flightContainer = document.getElementById('review-flight');
  if (flightContainer) {
    flightContainer.textContent = '';
    flightContainer.appendChild(createReviewRow('Flight', f.number));
    flightContainer.appendChild(createReviewRow('Route', f.departure.airport + ' → ' + f.arrival.airport));
    flightContainer.appendChild(createReviewRow('Date', f.departure.date));
    flightContainer.appendChild(createReviewRow('Departure', f.departure.time));
  }

  // Passengers
  let seatTotal = 0;
  const passengersContainer = document.getElementById('review-passengers');
  if (passengersContainer) {
    passengersContainer.textContent = '';
    BOOKING.passengers.forEach(p => {
      const seat = state.seats[p.id];
      const row = parseInt(seat);
      const isPremium = BOOKING.seatMap.premiumRows.includes(row);
      const cost = isPremium ? BOOKING.seatMap.premiumPrice : 0;
      seatTotal += cost;

      const valueText = 'Seat ' + seat + (cost > 0 ? ' (+$' + cost + ')' : '');
      passengersContainer.appendChild(createReviewRow(p.firstName + ' ' + p.lastName, valueText));
    });
  }

  // Baggage
  let baggageTotal = 0;
  const baggageContainer = document.getElementById('review-baggage');
  if (baggageContainer) {
    baggageContainer.textContent = '';
    let hasBaggage = false;

    BOOKING.passengers.forEach(p => {
      (state.baggage[p.id] || []).forEach(bagId => {
        const opt = BOOKING.baggage.find(o => o.id === bagId);
        if (opt) {
          hasBaggage = true;
          baggageTotal += opt.price;
          baggageContainer.appendChild(createReviewRow(p.firstName + ': ' + opt.name, '+$' + opt.price));
        }
      });
    });

    if (!hasBaggage) {
      baggageContainer.appendChild(createReviewRow('Included baggage only', '$0'));
    }
  }

  // Extras
  let extrasTotal = 0;
  const extrasContainer = document.getElementById('review-extras');
  if (extrasContainer) {
    extrasContainer.textContent = '';
    let hasExtras = false;

    state.extras.forEach(extId => {
      const opt = BOOKING.extras.find(o => o.id === extId);
      if (opt) {
        hasExtras = true;
        extrasTotal += opt.price;
        extrasContainer.appendChild(createReviewRow(opt.name, '+$' + opt.price));
      }
    });

    if (!hasExtras) {
      extrasContainer.appendChild(createReviewRow('No extras selected', '$0'));
    }
  }

  // Total
  const total = seatTotal + baggageTotal + extrasTotal;
  document.getElementById('review-total').textContent = '$' + total;
}

function confirmCheckIn() {
  showSpinner("Processing check-in...");

  setTimeout(() => {
    hideSpinner();
    goToSuccess();
  }, 2000);
}

// Success
function goToSuccess() {
  showStep('success');
  renderBoardingPasses();
}

// Helper to create boarding pass detail item
function createBpDetail(label, value) {
  const detail = document.createElement('div');
  detail.className = 'bp-detail';

  const labelDiv = document.createElement('div');
  labelDiv.className = 'bp-detail-label';
  labelDiv.textContent = label;
  detail.appendChild(labelDiv);

  const valueDiv = document.createElement('div');
  valueDiv.className = 'bp-detail-value';
  valueDiv.textContent = value;
  detail.appendChild(valueDiv);

  return detail;
}

function renderBoardingPasses() {
  const container = document.getElementById('boarding-passes');
  const f = BOOKING.flight;

  container.textContent = '';

  BOOKING.passengers.forEach(p => {
    const seat = state.seats[p.id];
    const qrId = 'qr-' + p.id;

    const boardingPass = document.createElement('div');
    boardingPass.className = 'boarding-pass';

    // Header
    const header = document.createElement('div');
    header.className = 'boarding-pass-header';

    const headerLeft = document.createElement('div');
    const airline = document.createElement('div');
    airline.className = 'bp-airline';
    airline.textContent = 'AnyCompany SPA';
    headerLeft.appendChild(airline);

    const flightDiv = document.createElement('div');
    flightDiv.className = 'bp-flight';
    flightDiv.textContent = 'Flight ' + f.number;
    headerLeft.appendChild(flightDiv);
    header.appendChild(headerLeft);

    const headerRight = document.createElement('div');
    headerRight.style.fontSize = '0.875rem';
    headerRight.textContent = 'Boarding Pass';
    header.appendChild(headerRight);

    boardingPass.appendChild(header);

    // Body
    const body = document.createElement('div');
    body.className = 'boarding-pass-body';

    // Route
    const route = document.createElement('div');
    route.className = 'bp-route';

    const depCity = document.createElement('div');
    depCity.className = 'bp-city';
    const depCode = document.createElement('div');
    depCode.className = 'bp-code';
    depCode.textContent = f.departure.airport;
    depCity.appendChild(depCode);
    const depName = document.createElement('div');
    depName.className = 'bp-name';
    depName.textContent = f.departure.city;
    depCity.appendChild(depName);
    route.appendChild(depCity);

    const arrow = document.createElement('div');
    arrow.className = 'bp-arrow';
    arrow.textContent = '✈';
    route.appendChild(arrow);

    const arrCity = document.createElement('div');
    arrCity.className = 'bp-city';
    const arrCode = document.createElement('div');
    arrCode.className = 'bp-code';
    arrCode.textContent = f.arrival.airport;
    arrCity.appendChild(arrCode);
    const arrName = document.createElement('div');
    arrName.className = 'bp-name';
    arrName.textContent = f.arrival.city;
    arrCity.appendChild(arrName);
    route.appendChild(arrCity);

    body.appendChild(route);

    // Passenger name
    const passenger = document.createElement('div');
    passenger.className = 'bp-passenger';
    passenger.textContent = p.firstName + ' ' + p.lastName;
    body.appendChild(passenger);

    // Details
    const details = document.createElement('div');
    details.className = 'bp-details';
    details.appendChild(createBpDetail('Date', f.departure.date));
    details.appendChild(createBpDetail('Boarding', f.departure.time));
    details.appendChild(createBpDetail('Gate', f.departure.gate));
    details.appendChild(createBpDetail('Seat', seat));
    body.appendChild(details);

    // QR Code placeholder
    const qrCode = document.createElement('div');
    qrCode.className = 'qr-code';
    qrCode.id = qrId;
    body.appendChild(qrCode);

    boardingPass.appendChild(body);
    container.appendChild(boardingPass);
  });

  // Generate QR codes
  BOOKING.passengers.forEach(p => {
    const qrContainer = document.getElementById('qr-' + p.id);
    if (qrContainer && typeof QRCode !== 'undefined') {
      new QRCode(qrContainer, {
        text: 'AEROJET-' + BOOKING.flight.number + '-' + p.firstName + '-' + state.seats[p.id],
        width: 100,
        height: 100,
        correctLevel: QRCode.CorrectLevel.M
      });
    } else if (qrContainer) {
      const fallback = document.createElement('div');
      fallback.style.cssText = 'text-align:center;color:var(--gray-400);font-size:0.75rem;';
      fallback.textContent = '[QR Code]';
      qrContainer.appendChild(fallback);
    }
  });
}

function downloadPasses() {
  const f = BOOKING.flight;
  let content = `AEROJET - BOARDING PASSES
${'='.repeat(50)}
Confirmation: ${BOOKING.confirmation}
Flight: ${f.number}
Route: ${f.departure.airport} (${f.departure.city}) → ${f.arrival.airport} (${f.arrival.city})
Date: ${f.departure.date}
Departure: ${f.departure.time}
Aircraft: ${f.aircraft}
${'='.repeat(50)}

`;

  BOOKING.passengers.forEach(p => {
    const seat = state.seats[p.id];
    content += `
PASSENGER: ${p.firstName} ${p.lastName}
Seat: ${seat}
Terminal: ${f.departure.terminal}
Gate: ${f.departure.gate}
Boarding Time: ${f.departure.time}
${'-'.repeat(50)}
`;
  });

  content += `
*** PLEASE ARRIVE AT THE GATE AT LEAST 30 MINUTES BEFORE DEPARTURE ***
`;

  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `boarding-passes-${BOOKING.confirmation}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function newCheckIn() {
  clearState();
  location.reload();
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadState();

  if (state.validated && state.currentStep && state.currentStep !== 'login') {
    showStep(state.currentStep);
    updateProgress();

    if (state.currentStep === 'seats') {
      renderSeatMap();
      renderPassengerPanel();
      updateSeatContinueButton();
    }
  } else {
    showStep('login');
  }
});
