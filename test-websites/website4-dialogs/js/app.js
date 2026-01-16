// AnyCompany Dialogs - International Travel Check-in
// Challenges: Conditional fields, passenger types, T&C scroll, multiple dialogs, dynamic dropdowns

const BOOKING = {
  confirmation: "GA7890",
  lastName: "Salazar",
  flight: {
    number: "GA456",
    route: { from: "JFK", to: "LHR" },
    fromCity: "New York",
    toCity: "London",
    date: "2025-01-28",
    time: "19:30",
    gate: "B44",
    terminal: "1",
    aircraft: "AnyPlane 900",
    international: true
  },
  passengers: [
    { id: 1, firstName: "Carlos", lastName: "Salazar", type: "adult", dob: "1985-03-15" },
    { id: 2, firstName: "Martha", lastName: "Salazar", type: "adult", dob: "1987-07-22" },
    { id: 3, firstName: "Sofía", lastName: "Salazar", type: "child", dob: "2015-11-08" },
    { id: 4, firstName: "Diego", lastName: "Salazar", type: "infant", dob: "2024-02-14" }
  ],
  seatMap: {
    rows: 20,
    columns: ["A", "B", "C", "D", "E", "F", "G", "H", "J"],
    premiumRows: [1, 2, 3, 4, 5],
    occupied: ["1A", "1B", "2D", "2E", "3G", "4A", "4H", "5C", "6B", "6F", "7A", "7J", "8D", "9B", "9E", "10A", "10G", "11C", "11H", "12B", "12F", "13A", "13E", "14D", "14J", "15B", "15G", "16A", "16F", "17C", "17H", "18B", "18E", "19A", "19G", "20D", "20J"],
    premiumPrice: 45
  },
  extras: [
    { id: "insurance", name: "Travel Insurance", price: 49, desc: "Comprehensive coverage including medical" },
    { id: "lounge", name: "Lounge Access", price: 65, desc: "Access to AnyCompany Dialogs Lounge at JFK" },
    { id: "wifi", name: "In-flight WiFi", price: 19, desc: "High-speed internet for the entire flight" },
    { id: "meal", name: "Premium Meal", price: 35, desc: "Three-course meal with wine pairing" },
    { id: "blanket", name: "Comfort Kit", price: 25, desc: "Blanket, pillow, and amenity kit" },
    { id: "fasttrack", name: "Fast Track Security", price: 29, desc: "Skip the queues at JFK security" }
  ]
};

// Country data for dynamic dropdowns
const COUNTRIES = [
  { code: "US", name: "United States" },
  { code: "GB", name: "United Kingdom" },
  { code: "CA", name: "Canada" },
  { code: "MX", name: "Mexico" },
  { code: "DE", name: "Germany" },
  { code: "FR", name: "France" },
  { code: "ES", name: "Spain" },
  { code: "IT", name: "Italy" },
  { code: "JP", name: "Japan" },
  { code: "AU", name: "Australia" },
  { code: "BR", name: "Brazil" },
  { code: "IN", name: "India" }
];

const STATES_BY_COUNTRY = {
  US: ["Alabama", "Alaska", "Arizona", "California", "Colorado", "Florida", "Georgia", "Hawaii", "Illinois", "New York", "Texas", "Washington"],
  GB: ["England", "Scotland", "Wales", "Northern Ireland"],
  CA: ["Alberta", "British Columbia", "Ontario", "Quebec", "Manitoba"],
  MX: ["Baja California", "Chihuahua", "Jalisco", "Mexico City", "Nuevo Leon"],
  DE: ["Bavaria", "Berlin", "Hamburg", "Hesse", "North Rhine-Westphalia"],
  FR: ["Île-de-France", "Provence", "Normandy", "Brittany", "Occitanie"],
  default: []
};

// State
const state = {
  validated: false,
  currentPassenger: 0,
  passengerData: {},
  seats: {},
  extras: [],
  termsRead: false,
  termsAccepted: false,
  pendingSeat: null
};

// XSS Protection: Escape HTML special characters
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// Load/save state
function loadState() {
  const saved = sessionStorage.getItem('globalair-state');
  if (saved) {
    const parsed = JSON.parse(saved);
    // Whitelist allowed state properties to prevent mass assignment vulnerabilities
    const allowedKeys = ['validated', 'currentPassenger', 'passengerData', 'seats', 'extras', 'termsRead', 'termsAccepted', 'pendingSeat'];
    const sanitizedData = Object.fromEntries(
      Object.entries(parsed).filter(([key]) => allowedKeys.includes(key))
    );
    Object.assign(state, sanitizedData);
  }
}

function saveState() {
  sessionStorage.setItem('globalair-state', JSON.stringify(state));
}

function clearState() {
  sessionStorage.removeItem('globalair-state');
}

// === LOGIN PAGE ===
function handleLookup() {
  // Ambiguous button - just shows a message
  alert('Looking up booking... Please click "Continue" to proceed.');
}

function handleLogin(event) {
  event.preventDefault();

  const code = document.getElementById('booking-ref').value.toUpperCase().trim();
  const name = document.getElementById('last-name').value.trim();

  const codeError = document.getElementById('booking-error');
  const nameError = document.getElementById('name-error');

  document.getElementById('booking-ref').classList.remove('error');
  document.getElementById('last-name').classList.remove('error');
  codeError.textContent = '';
  nameError.textContent = '';

  let valid = true;

  if (code !== BOOKING.confirmation) {
    document.getElementById('booking-ref').classList.add('error');
    codeError.textContent = 'Booking reference not found';
    valid = false;
  }

  if (name.toLowerCase() !== BOOKING.lastName.toLowerCase()) {
    document.getElementById('last-name').classList.add('error');
    nameError.textContent = 'Last name does not match';
    valid = false;
  }

  if (valid) {
    clearState();
    state.validated = true;
    saveState();
    window.location.href = 'passengers.html';
  }

  return false;
}

// === PASSENGERS PAGE ===
function initPassengers() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }
  renderPassengerForms();
}

function renderPassengerForms() {
  const container = document.getElementById('passengers-container');
  if (!container) return;

  container.innerHTML = '';

  BOOKING.passengers.forEach((p, idx) => {
    const savedData = state.passengerData[p.id] || {};
    const isComplete = isPassengerComplete(p.id);

    const card = document.createElement('div');
    card.className = 'passenger-card' + (isComplete ? ' complete' : '');
    card.id = 'passenger-' + p.id;

    // Header
    const header = document.createElement('div');
    header.className = 'passenger-card-header';

    const headerLeft = document.createElement('div');
    const nameStrong = document.createElement('strong');
    nameStrong.textContent = p.firstName + ' ' + p.lastName;
    headerLeft.appendChild(nameStrong);

    const typeSpan = document.createElement('span');
    typeSpan.className = 'passenger-type ' + p.type;
    typeSpan.textContent = p.type;
    headerLeft.appendChild(typeSpan);
    header.appendChild(headerLeft);

    if (isComplete) {
      const completeSpan = document.createElement('span');
      completeSpan.style.color = 'var(--success)';
      completeSpan.textContent = '✓ Complete';
      header.appendChild(completeSpan);
    }

    card.appendChild(header);

    // Infant assignment
    if (p.type === 'infant') {
      renderInfantAssignment(card, p, savedData);
    }

    // International flight requires passport
    if (BOOKING.flight.international) {
      const passportRow = document.createElement('div');
      passportRow.className = 'form-row';

      // Passport number group
      const passportGroup = document.createElement('div');
      passportGroup.className = 'form-group';

      const passportLabel = document.createElement('label');
      passportLabel.htmlFor = 'passport-' + p.id;
      passportLabel.textContent = 'Passport Number *';
      passportGroup.appendChild(passportLabel);

      const passportInput = document.createElement('input');
      passportInput.type = 'text';
      passportInput.id = 'passport-' + p.id;
      passportInput.value = savedData.passport || '';
      passportInput.placeholder = 'Enter passport number';
      passportInput.required = true;
      passportInput.onchange = function() { updatePassengerField(p.id, 'passport', this.value); };
      passportGroup.appendChild(passportInput);
      passportRow.appendChild(passportGroup);

      // Passport expiry group
      const expiryGroup = document.createElement('div');
      expiryGroup.className = 'form-group';

      const expiryLabel = document.createElement('label');
      expiryLabel.htmlFor = 'passport-exp-' + p.id;
      expiryLabel.textContent = 'Passport Expiry *';
      expiryGroup.appendChild(expiryLabel);

      const expiryInput = document.createElement('input');
      expiryInput.type = 'date';
      expiryInput.id = 'passport-exp-' + p.id;
      expiryInput.value = savedData.passportExpiry || '';
      expiryInput.required = true;
      expiryInput.onchange = function() { updatePassengerField(p.id, 'passportExpiry', this.value); };
      expiryGroup.appendChild(expiryInput);
      passportRow.appendChild(expiryGroup);

      card.appendChild(passportRow);
    }

    // Nationality row
    const nationalityRow = document.createElement('div');
    nationalityRow.className = 'form-row';

    // Nationality group
    const nationalityGroup = document.createElement('div');
    nationalityGroup.className = 'form-group';

    const nationalityLabel = document.createElement('label');
    nationalityLabel.htmlFor = 'nationality-' + p.id;
    nationalityLabel.textContent = 'Nationality *';
    nationalityGroup.appendChild(nationalityLabel);

    const nationalitySelect = document.createElement('select');
    nationalitySelect.id = 'nationality-' + p.id;
    nationalitySelect.onchange = function() { handleNationalityChange(p.id, this.value); };

    const defaultNatOption = document.createElement('option');
    defaultNatOption.value = '';
    defaultNatOption.textContent = 'Select country...';
    nationalitySelect.appendChild(defaultNatOption);

    nationalityGroup.appendChild(nationalitySelect);
    nationalityRow.appendChild(nationalityGroup);

    // State/Province group (conditional)
    const stateGroup = document.createElement('div');
    stateGroup.className = 'form-group conditional-field';
    stateGroup.id = 'state-group-' + p.id;

    const stateLabel = document.createElement('label');
    stateLabel.htmlFor = 'state-' + p.id;
    stateLabel.textContent = 'State/Province';
    stateGroup.appendChild(stateLabel);

    const stateSelect = document.createElement('select');
    stateSelect.id = 'state-' + p.id;
    stateSelect.onchange = function() { updatePassengerField(p.id, 'state', this.value); };

    const defaultStateOption = document.createElement('option');
    defaultStateOption.value = '';
    defaultStateOption.textContent = 'Loading...';
    stateSelect.appendChild(defaultStateOption);

    stateGroup.appendChild(stateSelect);
    nationalityRow.appendChild(stateGroup);

    card.appendChild(nationalityRow);

    // Visa group (conditional)
    const visaGroup = document.createElement('div');
    visaGroup.className = 'form-group conditional-field';
    visaGroup.id = 'visa-group-' + p.id;

    const visaLabel = document.createElement('label');
    visaLabel.htmlFor = 'visa-' + p.id;
    visaLabel.textContent = 'UK Visa Number (required for non-UK/EU citizens)';
    visaGroup.appendChild(visaLabel);

    const visaInput = document.createElement('input');
    visaInput.type = 'text';
    visaInput.id = 'visa-' + p.id;
    visaInput.value = savedData.visa || '';
    visaInput.placeholder = 'Enter visa number';
    visaInput.onchange = function() { updatePassengerField(p.id, 'visa', this.value); };
    visaGroup.appendChild(visaInput);

    card.appendChild(visaGroup);

    // Emergency contact for adults/children
    if (p.type !== 'infant') {
      const emergencyGroup = document.createElement('div');
      emergencyGroup.className = 'form-group';

      const emergencyLabel = document.createElement('label');
      emergencyLabel.htmlFor = 'emergency-' + p.id;
      emergencyLabel.textContent = 'Emergency Contact Phone';
      emergencyGroup.appendChild(emergencyLabel);

      const emergencyInput = document.createElement('input');
      emergencyInput.type = 'tel';
      emergencyInput.id = 'emergency-' + p.id;
      emergencyInput.value = savedData.emergency || '';
      emergencyInput.placeholder = '+1 555-123-4567';
      emergencyInput.onchange = function() { updatePassengerField(p.id, 'emergency', this.value); };
      emergencyGroup.appendChild(emergencyInput);

      card.appendChild(emergencyGroup);
    }

    container.appendChild(card);
  });

  // Load country dropdowns with delay (simulating API)
  BOOKING.passengers.forEach(p => {
    loadCountryDropdown(p.id);
  });

  updateContinueButton();
}

function renderInfantAssignment(parentElement, infant, savedData) {
  const adults = BOOKING.passengers.filter(p => p.type === 'adult');

  const assignmentDiv = document.createElement('div');
  assignmentDiv.className = 'infant-assignment';

  const label = document.createElement('label');
  label.htmlFor = 'infant-adult-' + infant.id;

  const labelStrong = document.createElement('strong');
  labelStrong.textContent = 'Assign infant to adult:';
  label.appendChild(labelStrong);
  label.appendChild(document.createTextNode(' Infants must be assigned to an adult passenger for seating'));
  assignmentDiv.appendChild(label);

  const select = document.createElement('select');
  select.id = 'infant-adult-' + infant.id;
  select.style.cssText = 'margin-top: 0.5rem; width: 100%;';
  select.onchange = function() { updatePassengerField(infant.id, 'assignedAdult', this.value); };

  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select adult...';
  select.appendChild(defaultOption);

  adults.forEach(a => {
    const option = document.createElement('option');
    option.value = a.id;
    option.textContent = a.firstName + ' ' + a.lastName;
    if (savedData.assignedAdult == a.id) {
      option.selected = true;
    }
    select.appendChild(option);
  });

  assignmentDiv.appendChild(select);
  parentElement.appendChild(assignmentDiv);
}

function loadCountryDropdown(passengerId) {
  const select = document.getElementById(`nationality-${passengerId}`);
  if (!select) return;

  // Add loading class
  select.classList.add('loading-options');

  // Simulate API delay
  setTimeout(() => {
    select.classList.remove('loading-options');

    const savedData = state.passengerData[passengerId] || {};

    // Clear and rebuild options using DOM manipulation
    select.innerHTML = '';

    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select country...';
    select.appendChild(defaultOption);

    COUNTRIES.forEach(c => {
      const option = document.createElement('option');
      option.value = c.code;
      option.textContent = c.name;
      if (savedData.nationality === c.code) {
        option.selected = true;
      }
      select.appendChild(option);
    });

    // If there was a saved nationality, trigger the state dropdown
    if (savedData.nationality) {
      handleNationalityChange(passengerId, savedData.nationality, false);
    }
  }, 800 + Math.random() * 500);
}

function handleNationalityChange(passengerId, countryCode, updateField = true) {
  if (updateField) {
    updatePassengerField(passengerId, 'nationality', countryCode);
  }

  const stateGroup = document.getElementById(`state-group-${passengerId}`);
  const visaGroup = document.getElementById(`visa-group-${passengerId}`);
  const stateSelect = document.getElementById(`state-${passengerId}`);

  // Show/hide state dropdown based on country
  if (countryCode && STATES_BY_COUNTRY[countryCode]) {
    stateGroup.classList.add('visible');

    // Simulate loading states
    stateSelect.innerHTML = '';
    const loadingOpt = document.createElement('option');
    loadingOpt.value = '';
    loadingOpt.textContent = 'Loading...';
    stateSelect.appendChild(loadingOpt);
    stateSelect.classList.add('loading-options');

    setTimeout(() => {
      stateSelect.classList.remove('loading-options');
      const states = STATES_BY_COUNTRY[countryCode] || STATES_BY_COUNTRY.default;
      const savedData = state.passengerData[passengerId] || {};

      // Clear and rebuild using DOM manipulation
      stateSelect.innerHTML = '';
      const defaultOpt = document.createElement('option');
      defaultOpt.value = '';
      defaultOpt.textContent = 'Select state/province...';
      stateSelect.appendChild(defaultOpt);

      states.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        if (savedData.state === s) {
          opt.selected = true;
        }
        stateSelect.appendChild(opt);
      });
    }, 600);
  } else {
    stateGroup.classList.remove('visible');
  }

  // Show visa field for non-UK/EU citizens going to UK
  const euCountries = ['GB', 'DE', 'FR', 'ES', 'IT'];
  if (countryCode && !euCountries.includes(countryCode) && BOOKING.flight.route.to === 'LHR') {
    visaGroup.classList.add('visible');
  } else {
    visaGroup.classList.remove('visible');
  }
}

function updatePassengerField(passengerId, field, value) {
  if (!state.passengerData[passengerId]) {
    state.passengerData[passengerId] = {};
  }
  state.passengerData[passengerId][field] = value;
  saveState();

  // Update card completion status
  const card = document.getElementById(`passenger-${passengerId}`);
  const isComplete = isPassengerComplete(passengerId);
  if (card) {
    card.classList.toggle('complete', isComplete);
  }

  updateContinueButton();
}

function isPassengerComplete(passengerId) {
  const passenger = BOOKING.passengers.find(p => p.id === passengerId);
  const data = state.passengerData[passengerId] || {};

  // Basic requirements
  if (!data.nationality) return false;

  // International flight requires passport
  if (BOOKING.flight.international) {
    if (!data.passport || !data.passportExpiry) return false;
  }

  // Infant must be assigned
  if (passenger.type === 'infant' && !data.assignedAdult) return false;

  // Visa required for non-EU to UK
  const euCountries = ['GB', 'DE', 'FR', 'ES', 'IT'];
  if (!euCountries.includes(data.nationality) && BOOKING.flight.route.to === 'LHR') {
    if (!data.visa) return false;
  }

  return true;
}

function updateContinueButton() {
  const btn = document.getElementById('continue-btn');
  if (!btn) return;

  const allComplete = BOOKING.passengers.every(p => isPassengerComplete(p.id));
  btn.disabled = !allComplete;
}

function saveProgress() {
  saveState();
  alert('Progress saved! You can continue later with the same booking reference.');
}

function handleContinue() {
  const page = document.body.dataset.page;

  switch (page) {
    case 'passengers':
      window.location.href = 'seats.html';
      break;
    case 'seats':
      window.location.href = 'extras.html';
      break;
    case 'extras':
      window.location.href = 'review.html';
      break;
  }
}

// === SEATS PAGE ===
function initSeats() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderPassengerTabs();
  renderSeatMap();
  renderSelectionSummary();
  updateSeatContinueButton();
}

function renderPassengerTabs() {
  const container = document.getElementById('passenger-tabs');
  if (!container) return;

  // Only show non-infant passengers (infants sit with adults)
  const seatablePassengers = BOOKING.passengers.filter(p => p.type !== 'infant');

  container.innerHTML = '';

  seatablePassengers.forEach((p, idx) => {
    const seat = state.seats[p.id];
    const isActive = idx === state.currentPassenger;

    const tab = document.createElement('div');
    tab.className = 'passenger-tab';
    if (isActive) tab.classList.add('active');
    if (seat) tab.classList.add('has-seat');
    tab.onclick = () => selectPassengerTab(idx);

    const nameDiv = document.createElement('div');
    nameDiv.className = 'passenger-tab-name';
    nameDiv.textContent = p.firstName;
    tab.appendChild(nameDiv);

    const seatDiv = document.createElement('div');
    seatDiv.className = 'passenger-tab-seat';
    seatDiv.textContent = seat ? 'Seat ' + seat : 'No seat selected';
    tab.appendChild(seatDiv);

    container.appendChild(tab);
  });
}

function selectPassengerTab(idx) {
  state.currentPassenger = idx;
  saveState();
  renderPassengerTabs();
  renderSeatMap();
}

function renderSeatMap() {
  const container = document.getElementById('seat-map');
  if (!container) return;

  const { rows, columns, premiumRows, occupied } = BOOKING.seatMap;
  const seatablePassengers = BOOKING.passengers.filter(p => p.type !== 'infant');
  const currentPassenger = seatablePassengers[state.currentPassenger];
  const selectedSeats = Object.values(state.seats);

  container.innerHTML = '';

  // Column headers row
  const headerRow = document.createElement('div');
  headerRow.className = 'seat-row';

  const emptyLabel = document.createElement('span');
  emptyLabel.className = 'row-label';
  headerRow.appendChild(emptyLabel);

  columns.forEach((col, idx) => {
    const colHeader = document.createElement('span');
    colHeader.className = 'col-header';
    colHeader.textContent = col;
    headerRow.appendChild(colHeader);

    if (idx === 2 || idx === 5) {
      const aisle = document.createElement('span');
      aisle.className = 'aisle';
      headerRow.appendChild(aisle);
    }
  });

  container.appendChild(headerRow);

  // Seat rows
  for (let row = 1; row <= rows; row++) {
    const seatRow = document.createElement('div');
    seatRow.className = 'seat-row';

    const rowLabel = document.createElement('span');
    rowLabel.className = 'row-label';
    rowLabel.textContent = row;
    seatRow.appendChild(rowLabel);

    columns.forEach((col, idx) => {
      const seatId = row + col;
      const isOccupied = occupied.includes(seatId);
      const isSelectedByOther = selectedSeats.includes(seatId) && state.seats[currentPassenger?.id] !== seatId;
      const isSelected = state.seats[currentPassenger?.id] === seatId;
      const isPremium = premiumRows.includes(row);

      const classes = ['seat'];
      let disabled = false;

      if (isOccupied || isSelectedByOther) {
        classes.push('occupied');
        disabled = true;
      } else if (isSelected) {
        classes.push('selected');
      } else if (isPremium) {
        classes.push('premium');
      } else {
        classes.push('available');
      }

      const button = document.createElement('button');
      button.className = classes.join(' ');
      button.setAttribute('aria-label', 'Seat ' + seatId);
      button.textContent = col;

      if (disabled) {
        button.disabled = true;
      } else {
        button.onclick = () => handleSeatClick(seatId, isPremium);
      }

      seatRow.appendChild(button);

      if (idx === 2 || idx === 5) {
        const aisle = document.createElement('span');
        aisle.className = 'aisle';
        seatRow.appendChild(aisle);
      }
    });

    container.appendChild(seatRow);
  }
}

function handleSeatClick(seatId, isPremium) {
  const seatablePassengers = BOOKING.passengers.filter(p => p.type !== 'infant');
  const currentPassenger = seatablePassengers[state.currentPassenger];

  state.pendingSeat = { seatId, isPremium, passengerId: currentPassenger.id };

  // First confirmation dialog
  document.getElementById('seat-confirm-message').textContent =
    `Select seat ${seatId} for ${currentPassenger.firstName}?`;
  document.getElementById('seat-confirm-modal').classList.add('active');
}

function closeSeatModal() {
  document.getElementById('seat-confirm-modal').classList.remove('active');
  state.pendingSeat = null;
}

function confirmSeatStep1() {
  document.getElementById('seat-confirm-modal').classList.remove('active');

  if (state.pendingSeat && state.pendingSeat.isPremium) {
    // Second confirmation for premium seats
    document.getElementById('premium-confirm-modal').classList.add('active');
  } else {
    finalizeSeatSelection();
  }
}

function closePremiumModal() {
  document.getElementById('premium-confirm-modal').classList.remove('active');
  state.pendingSeat = null;
}

function confirmPremiumSeat() {
  document.getElementById('premium-confirm-modal').classList.remove('active');
  finalizeSeatSelection();
}

function finalizeSeatSelection() {
  if (!state.pendingSeat) return;

  const { seatId, passengerId } = state.pendingSeat;

  // Toggle seat
  if (state.seats[passengerId] === seatId) {
    delete state.seats[passengerId];
  } else {
    state.seats[passengerId] = seatId;
  }

  state.pendingSeat = null;
  saveState();

  renderPassengerTabs();
  renderSeatMap();
  renderSelectionSummary();
  updateSeatContinueButton();
}

function renderSelectionSummary() {
  const container = document.getElementById('selection-summary');
  if (!container) return;

  container.innerHTML = '';

  const seatablePassengers = BOOKING.passengers.filter(p => p.type !== 'infant');
  let total = 0;

  const h3 = document.createElement('h3');
  h3.textContent = 'Selected Seats';
  container.appendChild(h3);

  seatablePassengers.forEach(p => {
    const seat = state.seats[p.id];
    let price = 0;

    if (seat) {
      const row = parseInt(seat);
      if (BOOKING.seatMap.premiumRows.includes(row)) {
        price = BOOKING.seatMap.premiumPrice;
        total += price;
      }
    }

    const reviewRow = document.createElement('div');
    reviewRow.className = 'review-row';

    const nameSpan = document.createElement('span');
    nameSpan.textContent = p.firstName;
    reviewRow.appendChild(nameSpan);

    const seatSpan = document.createElement('span');
    if (seat) {
      seatSpan.textContent = price > 0 ? seat + ' (+$' + price + ')' : seat;
    } else {
      seatSpan.textContent = '-';
    }
    reviewRow.appendChild(seatSpan);

    container.appendChild(reviewRow);
  });

  const totalRow = document.createElement('div');
  totalRow.className = 'review-row';
  totalRow.style.cssText = 'margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--gray-200); font-weight: 600;';

  const totalLabel = document.createElement('span');
  totalLabel.textContent = 'Seat Total';
  totalRow.appendChild(totalLabel);

  const totalValue = document.createElement('span');
  totalValue.textContent = '$' + total;
  totalRow.appendChild(totalValue);

  container.appendChild(totalRow);
}

function updateSeatContinueButton() {
  const btn = document.getElementById('continue-btn');
  if (!btn) return;

  const seatablePassengers = BOOKING.passengers.filter(p => p.type !== 'infant');
  const allSelected = seatablePassengers.every(p => state.seats[p.id]);
  btn.disabled = !allSelected;
}

// === EXTRAS PAGE ===
function initExtras() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderExtras();
  setupScrollReveal();
}

function renderExtras() {
  const container = document.getElementById('extras-container');
  if (!container) return;

  container.innerHTML = '';

  BOOKING.extras.forEach(ext => {
    const isSelected = state.extras.includes(ext.id);

    const label = document.createElement('label');
    label.className = 'extra-card' + (isSelected ? ' selected' : '');
    label.onclick = () => toggleExtra(ext.id);

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = isSelected;
    label.appendChild(checkbox);

    const nameDiv = document.createElement('div');
    nameDiv.className = 'extra-name';
    nameDiv.textContent = ext.name;
    label.appendChild(nameDiv);

    const descDiv = document.createElement('div');
    descDiv.className = 'extra-desc';
    descDiv.textContent = ext.desc;
    label.appendChild(descDiv);

    const priceDiv = document.createElement('div');
    priceDiv.className = 'extra-price';
    priceDiv.textContent = '+$' + ext.price;
    label.appendChild(priceDiv);

    container.appendChild(label);
  });
}

function toggleExtra(extraId) {
  const idx = state.extras.indexOf(extraId);
  if (idx === -1) {
    state.extras.push(extraId);
  } else {
    state.extras.splice(idx, 1);
  }
  saveState();
  renderExtras();
}

function setupScrollReveal() {
  // Hidden button appears after scrolling
  const skipBtn = document.getElementById('skip-btn');
  if (!skipBtn) return;

  setTimeout(() => {
    skipBtn.classList.add('visible');
  }, 2000);
}

function skipExtras() {
  state.extras = [];
  saveState();
  window.location.href = 'review.html';
}

// === REVIEW PAGE ===
function initReview() {
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderReviewContent();
  setupTermsScroll();
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

function renderReviewContent() {
  const container = document.getElementById('review-content');
  if (!container) return;

  container.innerHTML = '';
  const f = BOOKING.flight;

  // Flight details section
  const flightSection = document.createElement('div');
  flightSection.className = 'review-section';

  const flightH3 = document.createElement('h3');
  flightH3.textContent = 'Flight Details';
  flightSection.appendChild(flightH3);

  flightSection.appendChild(createReviewRow('Flight', f.number));
  flightSection.appendChild(createReviewRow('Route', f.fromCity + ' (' + f.route.from + ') → ' + f.toCity + ' (' + f.route.to + ')'));
  flightSection.appendChild(createReviewRow('Date', f.date));
  flightSection.appendChild(createReviewRow('Departure', f.time));
  flightSection.appendChild(createReviewRow('Terminal / Gate', f.terminal + ' / ' + f.gate));

  container.appendChild(flightSection);

  // Passengers section
  const passengersSection = document.createElement('div');
  passengersSection.className = 'review-section';

  const passengersH3 = document.createElement('h3');
  passengersH3.textContent = 'Passengers & Seats';
  passengersSection.appendChild(passengersH3);

  let seatTotal = 0;

  BOOKING.passengers.forEach(p => {
    const seat = state.seats[p.id];
    let seatInfo = '-';

    if (p.type === 'infant') {
      const assignedAdult = state.passengerData[p.id]?.assignedAdult;
      const adult = BOOKING.passengers.find(a => a.id == assignedAdult);
      seatInfo = adult ? 'With ' + adult.firstName : 'Not assigned';
    } else if (seat) {
      const row = parseInt(seat);
      const isPremium = BOOKING.seatMap.premiumRows.includes(row);
      if (isPremium) {
        seatTotal += BOOKING.seatMap.premiumPrice;
        seatInfo = seat + ' (+$' + BOOKING.seatMap.premiumPrice + ')';
      } else {
        seatInfo = seat;
      }
    }

    passengersSection.appendChild(createReviewRow(p.firstName + ' ' + p.lastName + ' (' + p.type + ')', seatInfo));
  });

  container.appendChild(passengersSection);

  // Extras section
  const extrasSection = document.createElement('div');
  extrasSection.className = 'review-section';

  const extrasH3 = document.createElement('h3');
  extrasH3.textContent = 'Extras';
  extrasSection.appendChild(extrasH3);

  let extrasTotal = 0;

  if (state.extras.length === 0) {
    extrasSection.appendChild(createReviewRow('No extras selected', '$0'));
  } else {
    state.extras.forEach(extId => {
      const ext = BOOKING.extras.find(e => e.id === extId);
      if (ext) {
        extrasTotal += ext.price;
        extrasSection.appendChild(createReviewRow(ext.name, '+$' + ext.price));
      }
    });
  }

  container.appendChild(extrasSection);

  // Update total
  const total = seatTotal + extrasTotal;
  document.getElementById('total-amount').textContent = `$${total}`;
  document.getElementById('modal-total').textContent = `$${total}`;
  document.getElementById('passenger-count').textContent = `${BOOKING.passengers.length} passengers`;
}

function setupTermsScroll() {
  const termsBox = document.getElementById('terms-box');
  const checkbox = document.getElementById('terms-checkbox');
  const checkboxHint = document.getElementById('checkbox-hint');
  const scrollHint = document.getElementById('scroll-hint');

  termsBox.addEventListener('scroll', () => {
    const isAtBottom = termsBox.scrollHeight - termsBox.scrollTop <= termsBox.clientHeight + 20;

    if (isAtBottom) {
      state.termsRead = true;
      checkbox.disabled = false;
      checkboxHint.classList.add('hidden');
      scrollHint.classList.add('hidden');
    }
  });

  checkbox.addEventListener('change', () => {
    state.termsAccepted = checkbox.checked;
    updateConfirmButton();
  });
}

function updateConfirmButton() {
  const btn = document.getElementById('confirm-btn');
  if (btn) {
    btn.disabled = !state.termsAccepted;
  }
}

function handleConfirm() {
  // Show final confirmation modal
  document.getElementById('final-confirm-modal').classList.add('active');
}

function closeFinalModal() {
  document.getElementById('final-confirm-modal').classList.remove('active');
}

function completeCheckIn() {
  closeFinalModal();
  saveState();
  window.location.href = 'success.html';
}

// === SUCCESS PAGE ===
function initSuccess() {
  renderBoardingPasses();
}

function renderBoardingPasses() {
  const container = document.getElementById('boarding-passes');
  if (!container) return;

  const f = BOOKING.flight;

  container.innerHTML = '';

  BOOKING.passengers.filter(p => p.type !== 'infant').forEach(p => {
    const seat = state.seats[p.id];

    const boardingPass = document.createElement('div');
    boardingPass.className = 'boarding-pass';

    // Header
    const header = document.createElement('div');
    header.className = 'boarding-pass-header';

    const headerLeft = document.createElement('div');
    const airline = document.createElement('strong');
    airline.textContent = 'AnyCompany Dialogs';
    headerLeft.appendChild(airline);

    const flightInfo = document.createElement('div');
    flightInfo.style.cssText = 'font-size: 0.875rem; opacity: 0.9;';
    flightInfo.textContent = 'Flight ' + f.number;
    headerLeft.appendChild(flightInfo);
    header.appendChild(headerLeft);

    const headerRight = document.createElement('div');
    headerRight.textContent = 'Boarding Pass';
    header.appendChild(headerRight);

    boardingPass.appendChild(header);

    // Body
    const body = document.createElement('div');
    body.className = 'boarding-pass-body';

    // Route
    const route = document.createElement('div');
    route.className = 'bp-route';

    const fromCity = document.createElement('div');
    fromCity.className = 'bp-city';
    const fromCode = document.createElement('div');
    fromCode.className = 'bp-code';
    fromCode.textContent = f.route.from;
    fromCity.appendChild(fromCode);
    const fromName = document.createElement('div');
    fromName.className = 'bp-name';
    fromName.textContent = f.fromCity;
    fromCity.appendChild(fromName);
    route.appendChild(fromCity);

    const arrow = document.createElement('div');
    arrow.className = 'bp-arrow';
    arrow.textContent = '✈';
    route.appendChild(arrow);

    const toCity = document.createElement('div');
    toCity.className = 'bp-city';
    const toCode = document.createElement('div');
    toCode.className = 'bp-code';
    toCode.textContent = f.route.to;
    toCity.appendChild(toCode);
    const toName = document.createElement('div');
    toName.className = 'bp-name';
    toName.textContent = f.toCity;
    toCity.appendChild(toName);
    route.appendChild(toCity);

    body.appendChild(route);

    // Passenger name
    const passenger = document.createElement('div');
    passenger.className = 'bp-passenger';
    passenger.textContent = p.firstName + ' ' + p.lastName;
    body.appendChild(passenger);

    // Details
    const details = document.createElement('div');
    details.className = 'bp-details';

    const detailItems = [
      { label: 'Date', value: f.date },
      { label: 'Boarding', value: f.time },
      { label: 'Gate', value: f.gate },
      { label: 'Seat', value: seat }
    ];

    detailItems.forEach(item => {
      const detailDiv = document.createElement('div');
      const labelDiv = document.createElement('div');
      labelDiv.className = 'bp-detail-label';
      labelDiv.textContent = item.label;
      detailDiv.appendChild(labelDiv);
      const valueDiv = document.createElement('div');
      valueDiv.className = 'bp-detail-value';
      valueDiv.textContent = item.value;
      detailDiv.appendChild(valueDiv);
      details.appendChild(detailDiv);
    });

    body.appendChild(details);
    boardingPass.appendChild(body);
    container.appendChild(boardingPass);
  });

  // Add infant info
  const infants = BOOKING.passengers.filter(p => p.type === 'infant');
  if (infants.length > 0) {
    const reminderBox = document.createElement('div');
    reminderBox.className = 'reminder-box';
    reminderBox.style.marginTop = '1rem';

    const h4 = document.createElement('h4');
    h4.textContent = 'Infant Passengers';
    reminderBox.appendChild(h4);

    infants.forEach(inf => {
      const assignedAdult = state.passengerData[inf.id]?.assignedAdult;
      const adult = BOOKING.passengers.find(a => a.id == assignedAdult);
      const p = document.createElement('p');
      p.textContent = inf.firstName + ' ' + inf.lastName + ' - traveling with ' + (adult ? adult.firstName : 'N/A');
      reminderBox.appendChild(p);
    });

    container.appendChild(reminderBox);
  }
}

function downloadPasses() {
  const f = BOOKING.flight;
  let content = `GLOBALAIR - BOARDING PASSES
${'='.repeat(50)}
Confirmation: ${BOOKING.confirmation}
Flight: ${f.number}
Route: ${f.fromCity} (${f.route.from}) → ${f.toCity} (${f.route.to})
Date: ${f.date}
Departure: ${f.time}
Aircraft: ${f.aircraft}
${'='.repeat(50)}

`;

  BOOKING.passengers.filter(p => p.type !== 'infant').forEach(p => {
    const seat = state.seats[p.id];
    content += `
PASSENGER: ${p.firstName} ${p.lastName}
Seat: ${seat}
Terminal: ${f.terminal}
Gate: ${f.gate}
Boarding Time: ${f.time}
${'-'.repeat(50)}
`;
  });

  // Add infant info
  const infants = BOOKING.passengers.filter(p => p.type === 'infant');
  if (infants.length > 0) {
    content += `
INFANT PASSENGERS:
`;
    infants.forEach(inf => {
      const assignedAdult = state.passengerData[inf.id]?.assignedAdult;
      const adult = BOOKING.passengers.find(a => a.id == assignedAdult);
      content += `${inf.firstName} ${inf.lastName} - traveling with ${adult ? adult.firstName : 'N/A'}\n`;
    });
  }

  content += `
${'='.repeat(50)}
*** INTERNATIONAL FLIGHT - ARRIVE 3 HOURS BEFORE DEPARTURE ***
*** HAVE PASSPORT AND VISA READY AT CHECK-IN ***
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
  window.location.href = 'index.html';
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
  loadState();

  const page = document.body.dataset.page;
  switch (page) {
    case 'passengers': initPassengers(); break;
    case 'seats': initSeats(); break;
    case 'extras': initExtras(); break;
    case 'review': initReview(); break;
    case 'success': initSuccess(); break;
  }
});
