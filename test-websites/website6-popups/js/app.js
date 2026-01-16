// AnyCompany Popups - Main Application JavaScript
// Challenges: Cookie banner, date picker, autocomplete, promotional overlay

// ===================
// STATE MANAGEMENT
// ===================
const state = {
  cookiesAccepted: false,
  currentPage: null,
  booking: null,
  passengers: [],
  seats: {},
  baggage: {},
  selectedCompanion: null,
  currentPassengerIndex: 0,
  pendingSeat: null,
  promoAccepted: false,
  termsRead: false,
  termsAccepted: false
};

// Test booking data
const TEST_BOOKING = {
  confirmationCode: 'PS1234',
  lastName: 'Jackson',
  departureDate: '2025-02-15',
  flight: {
    number: 'PS789',
    origin: 'SFO',
    originCity: 'San Francisco',
    destination: 'HNL',
    destinationCity: 'Honolulu',
    date: 'Feb 15, 2025',
    time: '08:30',
    aircraft: 'AnyPlane 700'
  },
  passengers: [
    { id: 1, firstName: 'Mateo', lastName: 'Jackson', type: 'Adult' }
  ]
};

// Frequent flyer database for autocomplete
const FREQUENT_FLYERS = [
  { id: 'FF001', name: 'Sarah Jackson', number: 'PS-123456', tier: 'Gold' },
  { id: 'FF002', name: 'James Wilson', number: 'PS-234567', tier: 'Silver' },
  { id: 'FF003', name: 'Emily Davis', number: 'PS-345678', tier: 'Platinum' },
  { id: 'FF004', name: 'Robert Brown', number: 'PS-456789', tier: 'Gold' },
  { id: 'FF005', name: 'Jennifer Martinez', number: 'PS-567890', tier: 'Silver' },
  { id: 'FF006', name: 'David Jackson', number: 'PS-678901', tier: 'Bronze' },
  { id: 'FF007', name: 'Lisa Anderson', number: 'PS-789012', tier: 'Gold' },
  { id: 'FF008', name: 'Mateo Chen', number: 'PS-890123', tier: 'Platinum' },
  { id: 'FF009', name: 'Amanda Taylor', number: 'PS-901234', tier: 'Silver' },
  { id: 'FF010', name: 'Christopher Lee', number: 'PS-012345', tier: 'Bronze' }
];

// Seat configuration
const SEAT_CONFIG = {
  rows: 25,
  columns: ['A', 'B', 'C', 'D', 'E', 'F'],
  premiumRows: [1, 2, 3, 4, 5],
  exitRows: [12, 13],
  occupiedSeats: ['1A', '1F', '2C', '3B', '5A', '5F', '7C', '7D', '8A', '9E', '10F',
                  '12A', '12F', '14B', '15C', '16D', '17A', '18E', '19F', '20B',
                  '21C', '22A', '23D', '24E', '25F']
};

// ===================
// INITIALIZATION
// ===================
document.addEventListener('DOMContentLoaded', () => {
  state.currentPage = document.body.dataset.page;

  // Load state from session storage
  loadState();

  // Initialize based on current page
  switch (state.currentPage) {
    case 'login':
      initLoginPage();
      break;
    case 'passengers':
      initPassengersPage();
      break;
    case 'seats':
      initSeatsPage();
      break;
    case 'baggage':
      initBaggagePage();
      break;
    case 'review':
      initReviewPage();
      break;
    case 'success':
      initSuccessPage();
      break;
  }
});

function loadState() {
  const saved = sessionStorage.getItem('pacificsky_state');
  if (saved) {
    const parsed = JSON.parse(saved);
    // Whitelist allowed state properties to prevent mass assignment vulnerabilities
    const allowedKeys = ['cookiesAccepted', 'currentPage', 'booking', 'passengers', 'seats', 'baggage', 'selectedCompanion', 'currentPassengerIndex', 'pendingSeat', 'promoAccepted', 'termsRead', 'termsAccepted', 'seatPrices', 'baggagePrices'];
    const sanitizedData = Object.fromEntries(
      Object.entries(parsed).filter(([key]) => allowedKeys.includes(key))
    );
    Object.assign(state, sanitizedData);
  }
}

function saveState() {
  sessionStorage.setItem('pacificsky_state', JSON.stringify(state));
}

// ===================
// COOKIE CONSENT BANNER
// ===================
function handleAcceptCookies() {
  state.cookiesAccepted = true;
  saveState();
  hideCookieBanner();
}

function handleRejectCookies() {
  state.cookiesAccepted = true; // Still hide banner
  saveState();
  hideCookieBanner();
}

function handleCookieSettings() {
  document.getElementById('cookie-settings-modal').classList.add('active');
}

function closeCookieSettings() {
  document.getElementById('cookie-settings-modal').classList.remove('active');
}

function saveCookieSettings() {
  state.cookiesAccepted = true;
  saveState();
  closeCookieSettings();
  hideCookieBanner();
}

function hideCookieBanner() {
  const banner = document.getElementById('cookie-banner');
  if (banner) {
    banner.classList.add('hidden');
  }
}

function checkCookieConsent() {
  if (state.cookiesAccepted) {
    hideCookieBanner();
    return true;
  }
  return false;
}

// ===================
// LOGIN PAGE
// ===================
function initLoginPage() {
  // Check if cookies already accepted
  checkCookieConsent();

  // Initialize date picker
  initDatePicker();
}

// ===================
// DATE PICKER
// ===================
let datePickerState = {
  currentMonth: new Date().getMonth(),
  currentYear: new Date().getFullYear(),
  selectedDate: null
};

function initDatePicker() {
  renderCalendar();

  // Close on click outside (on the overlay background)
  const overlay = document.getElementById('date-picker-overlay');
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      // Only close if clicking the overlay itself, not the calendar
      if (e.target === overlay) {
        closeDatePicker();
      }
    });
  }
}

function toggleDatePicker() {
  const overlay = document.getElementById('date-picker-overlay');
  if (overlay.classList.contains('active')) {
    closeDatePicker();
  } else {
    overlay.classList.add('active');
    renderCalendar();
  }
}

function closeDatePicker() {
  const overlay = document.getElementById('date-picker-overlay');
  if (overlay) {
    overlay.classList.remove('active');
  }
}

function prevMonth() {
  datePickerState.currentMonth--;
  if (datePickerState.currentMonth < 0) {
    datePickerState.currentMonth = 11;
    datePickerState.currentYear--;
  }
  renderCalendar();
}

function nextMonth() {
  datePickerState.currentMonth++;
  if (datePickerState.currentMonth > 11) {
    datePickerState.currentMonth = 0;
    datePickerState.currentYear++;
  }
  renderCalendar();
}

function renderCalendar() {
  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                      'July', 'August', 'September', 'October', 'November', 'December'];

  // Update header
  document.getElementById('current-month').textContent =
    `${monthNames[datePickerState.currentMonth]} ${datePickerState.currentYear}`;

  const daysContainer = document.getElementById('date-picker-days');
  daysContainer.textContent = '';

  const firstDay = new Date(datePickerState.currentYear, datePickerState.currentMonth, 1).getDay();
  const daysInMonth = new Date(datePickerState.currentYear, datePickerState.currentMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(datePickerState.currentYear, datePickerState.currentMonth, 0).getDate();

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Previous month days
  for (let i = firstDay - 1; i >= 0; i--) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = daysInPrevMonth - i;
    btn.className = 'other-month';
    btn.disabled = true;
    daysContainer.appendChild(btn);
  }

  // Current month days
  for (let day = 1; day <= daysInMonth; day++) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = day;

    const date = new Date(datePickerState.currentYear, datePickerState.currentMonth, day);
    date.setHours(0, 0, 0, 0);

    // Check if today
    if (date.getTime() === today.getTime()) {
      btn.classList.add('today');
    }

    // Check if selected
    if (datePickerState.selectedDate) {
      const selected = new Date(datePickerState.selectedDate);
      selected.setHours(0, 0, 0, 0);
      if (date.getTime() === selected.getTime()) {
        btn.classList.add('selected');
      }
    }

    // Disable past dates (except for testing)
    // For testing purposes, we allow past dates

    btn.onclick = () => selectDate(date);
    daysContainer.appendChild(btn);
  }

  // Next month days
  const totalCells = Math.ceil((firstDay + daysInMonth) / 7) * 7;
  const remaining = totalCells - firstDay - daysInMonth;
  for (let i = 1; i <= remaining; i++) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = i;
    btn.className = 'other-month';
    btn.disabled = true;
    daysContainer.appendChild(btn);
  }
}

function selectDate(date) {
  datePickerState.selectedDate = date;

  // Format date for display
  const options = { year: 'numeric', month: 'short', day: 'numeric' };
  document.getElementById('departure-date').value = date.toLocaleDateString('en-US', options);

  // Store in ISO format for validation
  document.getElementById('departure-date').dataset.isoDate =
    `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

  // Close picker modal
  closeDatePicker();

  // Re-render to show selection
  renderCalendar();
}

// ===================
// LOGIN HANDLER
// ===================
function handleLogin(event) {
  event.preventDefault();

  // Check cookie consent first
  if (!state.cookiesAccepted) {
    alert('Please accept or configure cookie preferences to continue.');
    return false;
  }

  const bookingRef = document.getElementById('booking-ref').value.trim().toUpperCase();
  const lastName = document.getElementById('last-name').value.trim();
  const dateInput = document.getElementById('departure-date');
  const selectedDate = dateInput.dataset.isoDate;

  // Clear errors
  document.getElementById('booking-error').textContent = '';
  document.getElementById('name-error').textContent = '';
  document.getElementById('date-error').textContent = '';

  let hasError = false;

  // Validate booking reference
  if (bookingRef !== TEST_BOOKING.confirmationCode) {
    document.getElementById('booking-error').textContent = 'Booking not found';
    document.getElementById('booking-ref').classList.add('error');
    hasError = true;
  }

  // Validate last name
  if (lastName.toLowerCase() !== TEST_BOOKING.lastName.toLowerCase()) {
    document.getElementById('name-error').textContent = 'Last name does not match';
    document.getElementById('last-name').classList.add('error');
    hasError = true;
  }

  // Validate date
  if (!selectedDate) {
    document.getElementById('date-error').textContent = 'Please select a departure date';
    hasError = true;
  } else if (selectedDate !== TEST_BOOKING.departureDate) {
    document.getElementById('date-error').textContent = 'Date does not match booking';
    hasError = true;
  }

  if (hasError) {
    return false;
  }

  // Success - save booking and navigate
  state.booking = TEST_BOOKING;
  state.passengers = [...TEST_BOOKING.passengers];
  saveState();

  window.location.href = 'passengers.html';
  return false;
}

// ===================
// PASSENGERS PAGE
// ===================
function initPassengersPage() {
  if (!state.booking) {
    window.location.href = 'index.html';
    return;
  }

  renderPassengers();
  validatePassengersForm();
}

function renderPassengers() {
  const container = document.getElementById('passengers-container');
  container.textContent = '';

  state.passengers.forEach((passenger, index) => {
    const card = document.createElement('div');
    card.className = 'passenger-card';

    // Header
    const header = document.createElement('div');
    header.className = 'passenger-header';
    const nameSpan = document.createElement('span');
    nameSpan.className = 'passenger-name';
    nameSpan.textContent = `Passenger ${index + 1}: ${passenger.firstName} ${passenger.lastName}`;
    const typeSpan = document.createElement('span');
    typeSpan.textContent = passenger.type;
    header.appendChild(nameSpan);
    header.appendChild(typeSpan);

    // First form row (names)
    const formRow1 = document.createElement('div');
    formRow1.className = 'form-row';

    const firstNameGroup = document.createElement('div');
    firstNameGroup.className = 'form-group';
    const firstNameLabel = document.createElement('label');
    firstNameLabel.textContent = 'First Name';
    const firstNameInput = document.createElement('input');
    firstNameInput.type = 'text';
    firstNameInput.value = passenger.firstName;
    firstNameInput.required = true;
    firstNameInput.addEventListener('change', function() { updatePassenger(index, 'firstName', this.value); });
    firstNameGroup.appendChild(firstNameLabel);
    firstNameGroup.appendChild(firstNameInput);

    const lastNameGroup = document.createElement('div');
    lastNameGroup.className = 'form-group';
    const lastNameLabel = document.createElement('label');
    lastNameLabel.textContent = 'Last Name';
    const lastNameInput = document.createElement('input');
    lastNameInput.type = 'text';
    lastNameInput.value = passenger.lastName;
    lastNameInput.required = true;
    lastNameInput.addEventListener('change', function() { updatePassenger(index, 'lastName', this.value); });
    lastNameGroup.appendChild(lastNameLabel);
    lastNameGroup.appendChild(lastNameInput);

    formRow1.appendChild(firstNameGroup);
    formRow1.appendChild(lastNameGroup);

    // Second form row (dob, gender)
    const formRow2 = document.createElement('div');
    formRow2.className = 'form-row';

    const dobGroup = document.createElement('div');
    dobGroup.className = 'form-group';
    const dobLabel = document.createElement('label');
    dobLabel.textContent = 'Date of Birth';
    const dobInput = document.createElement('input');
    dobInput.type = 'date';
    dobInput.value = passenger.dob || '';
    dobInput.required = true;
    dobInput.addEventListener('change', function() { updatePassenger(index, 'dob', this.value); });
    dobGroup.appendChild(dobLabel);
    dobGroup.appendChild(dobInput);

    const genderGroup = document.createElement('div');
    genderGroup.className = 'form-group';
    const genderLabel = document.createElement('label');
    genderLabel.textContent = 'Gender';
    const genderSelect = document.createElement('select');
    genderSelect.required = true;
    genderSelect.addEventListener('change', function() { updatePassenger(index, 'gender', this.value); });
    const genderOptions = [
      { value: '', text: 'Select...' },
      { value: 'M', text: 'Male' },
      { value: 'F', text: 'Female' },
      { value: 'X', text: 'Other' }
    ];
    genderOptions.forEach(opt => {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.text;
      if (passenger.gender === opt.value) option.selected = true;
      genderSelect.appendChild(option);
    });
    genderGroup.appendChild(genderLabel);
    genderGroup.appendChild(genderSelect);

    formRow2.appendChild(dobGroup);
    formRow2.appendChild(genderGroup);

    card.appendChild(header);
    card.appendChild(formRow1);
    card.appendChild(formRow2);
    container.appendChild(card);
  });
}

function updatePassenger(index, field, value) {
  state.passengers[index][field] = value;
  saveState();
  validatePassengersForm();
}

function validatePassengersForm() {
  const allValid = state.passengers.every(p =>
    p.firstName && p.lastName && p.dob && p.gender
  );
  document.getElementById('continue-btn').disabled = !allValid;
}

// ===================
// AUTOCOMPLETE
// ===================
let autocompleteTimeout = null;
let autocompleteVisible = false;

function handleAutocompleteInput(value) {
  clearTimeout(autocompleteTimeout);

  if (value.length < 2) {
    hideAutocomplete();
    return;
  }

  // Show loading state
  showAutocompleteLoading();

  // Simulate API delay
  autocompleteTimeout = setTimeout(() => {
    const results = searchFrequentFlyers(value);
    showAutocompleteResults(results);
  }, 500);
}

function searchFrequentFlyers(query) {
  query = query.toLowerCase();
  return FREQUENT_FLYERS.filter(ff =>
    ff.name.toLowerCase().includes(query) ||
    ff.number.toLowerCase().includes(query)
  );
}

function showAutocomplete() {
  const dropdown = document.getElementById('autocomplete-dropdown');
  dropdown.classList.add('active');
  autocompleteVisible = true;
}

function hideAutocomplete() {
  const dropdown = document.getElementById('autocomplete-dropdown');
  dropdown.classList.remove('active');
  document.getElementById('autocomplete-loading').classList.remove('active');
  document.getElementById('autocomplete-results').classList.remove('active');
  document.getElementById('autocomplete-no-results').classList.remove('active');
  autocompleteVisible = false;
}

function hideAutocompleteDelayed() {
  setTimeout(() => {
    if (!document.querySelector('.autocomplete-dropdown:hover')) {
      hideAutocomplete();
    }
  }, 200);
}

function showAutocompleteLoading() {
  showAutocomplete();
  document.getElementById('autocomplete-loading').classList.add('active');
  document.getElementById('autocomplete-results').classList.remove('active');
  document.getElementById('autocomplete-no-results').classList.remove('active');
}

function showAutocompleteResults(results) {
  document.getElementById('autocomplete-loading').classList.remove('active');

  if (results.length === 0) {
    document.getElementById('autocomplete-no-results').classList.add('active');
    document.getElementById('autocomplete-results').classList.remove('active');
    return;
  }

  const container = document.getElementById('autocomplete-results');
  container.textContent = '';

  results.forEach(ff => {
    const item = document.createElement('div');
    item.className = 'autocomplete-item';

    const nameDiv = document.createElement('div');
    nameDiv.className = 'name';
    nameDiv.textContent = ff.name;

    const detailsDiv = document.createElement('div');
    detailsDiv.className = 'details';
    detailsDiv.textContent = `${ff.number} • ${ff.tier} Member`;

    item.appendChild(nameDiv);
    item.appendChild(detailsDiv);
    item.addEventListener('click', () => selectCompanion(ff));
    container.appendChild(item);
  });

  container.classList.add('active');
  document.getElementById('autocomplete-no-results').classList.remove('active');
}

function selectCompanion(ff) {
  state.selectedCompanion = ff;

  // Add as passenger
  const newPassenger = {
    id: state.passengers.length + 1,
    firstName: ff.name.split(' ')[0],
    lastName: ff.name.split(' ').slice(1).join(' '),
    type: 'Adult',
    frequentFlyer: ff.number
  };
  state.passengers.push(newPassenger);
  saveState();

  // Update UI
  document.getElementById('companion-search').value = '';
  hideAutocomplete();

  document.getElementById('companion-name').textContent = ff.name;
  document.getElementById('companion-number').textContent = `${ff.number} • ${ff.tier}`;
  document.getElementById('selected-companion').style.display = 'flex';
  document.getElementById('add-passenger-section').querySelector('.form-group').style.display = 'none';

  renderPassengers();
}

function removeCompanion() {
  if (state.selectedCompanion) {
    state.passengers = state.passengers.filter(p => p.frequentFlyer !== state.selectedCompanion.number);
    state.selectedCompanion = null;
    saveState();

    document.getElementById('selected-companion').style.display = 'none';
    document.getElementById('add-passenger-section').querySelector('.form-group').style.display = 'block';

    renderPassengers();
  }
}

// ===================
// SEATS PAGE
// ===================
let promoTimer = null;
let seatAlertTimeout = null;

function initSeatsPage() {
  if (!state.booking) {
    window.location.href = 'index.html';
    return;
  }

  renderPassengerTabs();
  renderSeatMap();
  updateSelectionSummary();

  // Show promo overlay after 5 seconds (if not already accepted/dismissed)
  if (!state.promoAccepted && !sessionStorage.getItem('promo_dismissed')) {
    setTimeout(showPromoOverlay, 5000);
  }

  // Show upgrade badge if promo was accepted
  if (state.promoAccepted) {
    document.getElementById('upgrade-badge').style.display = 'block';
  }

  // Show seat alert after 15 seconds
  setTimeout(showSeatAlert, 15000);
}

function renderPassengerTabs() {
  const container = document.getElementById('passenger-tabs');
  container.textContent = '';

  state.passengers.forEach((passenger, index) => {
    const tab = document.createElement('div');
    tab.className = `passenger-tab ${index === state.currentPassengerIndex ? 'active' : ''} ${state.seats[passenger.id] ? 'has-seat' : ''}`;

    const nameDiv = document.createElement('div');
    nameDiv.className = 'passenger-tab-name';
    nameDiv.textContent = `${passenger.firstName} ${passenger.lastName}`;

    const seatDiv = document.createElement('div');
    seatDiv.className = 'passenger-tab-seat';
    seatDiv.textContent = state.seats[passenger.id] || 'No seat selected';

    tab.appendChild(nameDiv);
    tab.appendChild(seatDiv);
    tab.addEventListener('click', () => selectPassengerTab(index));
    container.appendChild(tab);
  });
}

function selectPassengerTab(index) {
  state.currentPassengerIndex = index;
  renderPassengerTabs();
  renderSeatMap();
}

function renderSeatMap() {
  const container = document.getElementById('seat-map');
  container.textContent = '';

  // Column headers
  const headerRow = document.createElement('div');
  headerRow.className = 'seat-row';
  const emptyLabel = document.createElement('div');
  emptyLabel.className = 'row-label';
  headerRow.appendChild(emptyLabel);

  SEAT_CONFIG.columns.forEach((col, i) => {
    const colHeader = document.createElement('div');
    colHeader.className = 'col-header';
    colHeader.textContent = col;
    headerRow.appendChild(colHeader);
    if (i === 2) {
      const aisleDiv = document.createElement('div');
      aisleDiv.className = 'aisle';
      headerRow.appendChild(aisleDiv);
    }
  });
  container.appendChild(headerRow);

  // Seat rows
  for (let row = 1; row <= SEAT_CONFIG.rows; row++) {
    const rowDiv = document.createElement('div');
    rowDiv.className = 'seat-row';
    const rowLabel = document.createElement('div');
    rowLabel.className = 'row-label';
    rowLabel.textContent = row;
    rowDiv.appendChild(rowLabel);

    SEAT_CONFIG.columns.forEach((col, i) => {
      const seatId = `${row}${col}`;
      const seat = document.createElement('button');
      seat.className = 'seat';
      seat.textContent = seatId;

      // Determine seat type
      if (SEAT_CONFIG.occupiedSeats.includes(seatId)) {
        seat.classList.add('occupied');
        seat.disabled = true;
      } else if (Object.values(state.seats).includes(seatId)) {
        seat.classList.add('selected');
      } else if (SEAT_CONFIG.exitRows.includes(row)) {
        seat.classList.add('exit');
      } else if (SEAT_CONFIG.premiumRows.includes(row)) {
        seat.classList.add('premium');
      } else {
        seat.classList.add('available');
      }

      if (!seat.disabled) {
        seat.onclick = () => handleSeatClick(seatId, row);
      }

      rowDiv.appendChild(seat);

      // Add aisle
      if (i === 2) {
        const aisle = document.createElement('div');
        aisle.className = 'aisle';
        rowDiv.appendChild(aisle);
      }
    });

    container.appendChild(rowDiv);
  }
}

function handleSeatClick(seatId, row) {
  const currentPassenger = state.passengers[state.currentPassengerIndex];

  // Check if this seat is already selected by another passenger
  const existingPassengerId = Object.keys(state.seats).find(id => state.seats[id] === seatId);
  if (existingPassengerId && existingPassengerId != currentPassenger.id) {
    alert('This seat is already selected by another passenger.');
    return;
  }

  // Calculate price
  let price = 0;
  let seatType = 'Standard';
  if (SEAT_CONFIG.exitRows.includes(row)) {
    price = 45;
    seatType = 'Exit Row';
  } else if (SEAT_CONFIG.premiumRows.includes(row)) {
    price = 35;
    seatType = 'Premium';
  }

  // Show confirmation modal
  state.pendingSeat = { seatId, row, price, seatType };
  document.getElementById('seat-modal-message').textContent =
    `Select seat ${seatId} for ${currentPassenger.firstName} ${currentPassenger.lastName}?`;
  const modalDetails = document.getElementById('seat-modal-details');
  modalDetails.textContent = '';

  const seatPara = document.createElement('p');
  const seatStrong = document.createElement('strong');
  seatStrong.textContent = 'Seat: ';
  seatPara.appendChild(seatStrong);
  seatPara.appendChild(document.createTextNode(seatId + ' (' + seatType + ')'));
  modalDetails.appendChild(seatPara);

  const costPara = document.createElement('p');
  if (price > 0) {
    const costStrong = document.createElement('strong');
    costStrong.textContent = 'Additional Cost: ';
    costPara.appendChild(costStrong);
    costPara.appendChild(document.createTextNode('$' + price));
  } else {
    costPara.textContent = 'No additional cost';
  }
  modalDetails.appendChild(costPara);
  document.getElementById('seat-modal').classList.add('active');
}

function closeSeatModal() {
  document.getElementById('seat-modal').classList.remove('active');
  state.pendingSeat = null;
}

function confirmSeatSelection() {
  if (!state.pendingSeat) return;

  const currentPassenger = state.passengers[state.currentPassengerIndex];
  const { seatId, price } = state.pendingSeat;

  // Update state
  state.seats[currentPassenger.id] = seatId;
  if (!state.seatPrices) state.seatPrices = {};
  state.seatPrices[currentPassenger.id] = price;
  saveState();

  // Close modal and refresh
  closeSeatModal();
  renderPassengerTabs();
  renderSeatMap();
  updateSelectionSummary();
  updateContinueButton();
}

function updateSelectionSummary() {
  const container = document.getElementById('selection-summary');
  container.textContent = '';

  let total = 0;

  state.passengers.forEach(passenger => {
    const seat = state.seats[passenger.id];
    const price = state.seatPrices?.[passenger.id] || 0;
    total += price;

    if (seat) {
      const item = document.createElement('div');
      item.className = 'selection-item';

      const nameSpan = document.createElement('span');
      nameSpan.textContent = passenger.firstName + ': ' + seat;

      const priceSpan = document.createElement('span');
      priceSpan.textContent = price > 0 ? '$' + price : 'Free';

      item.appendChild(nameSpan);
      item.appendChild(priceSpan);
      container.appendChild(item);
    }
  });

  document.getElementById('seat-total').textContent = '$' + total;
}

function updateContinueButton() {
  const allSeatsSelected = state.passengers.every(p => state.seats[p.id]);
  document.getElementById('continue-btn').disabled = !allSeatsSelected;
}

// ===================
// PROMOTIONAL OVERLAY
// ===================
function showPromoOverlay() {
  document.getElementById('promo-overlay').classList.add('active');
  startPromoCountdown();
}

function closePromoOverlay() {
  document.getElementById('promo-overlay').classList.remove('active');
  clearInterval(promoTimer);
  sessionStorage.setItem('promo_dismissed', 'true');
}

function acceptPromoOffer() {
  state.promoAccepted = true;
  saveState();
  closePromoOverlay();
  document.getElementById('upgrade-badge').style.display = 'block';
}

function startPromoCountdown() {
  let seconds = 299; // 4:59

  promoTimer = setInterval(() => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    document.getElementById('promo-countdown').textContent =
      `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

    if (seconds <= 0) {
      clearInterval(promoTimer);
      closePromoOverlay();
    }
    seconds--;
  }, 1000);
}

// ===================
// SEAT ALERT
// ===================
const ALERT_MESSAGES = [
  'Seat 12A was just taken by another passenger',
  'Window seats in rows 8-10 are filling fast!',
  'Exit row seats (extra legroom) almost sold out',
  'Seat 5F was just selected by another customer'
];

function showSeatAlert() {
  const message = ALERT_MESSAGES[Math.floor(Math.random() * ALERT_MESSAGES.length)];
  document.getElementById('alert-message').textContent = message;
  document.getElementById('seat-alert').classList.add('active');

  // Auto-hide after 8 seconds
  seatAlertTimeout = setTimeout(closeSeatAlert, 8000);
}

function closeSeatAlert() {
  document.getElementById('seat-alert').classList.remove('active');
  clearTimeout(seatAlertTimeout);
}

// ===================
// BAGGAGE PAGE
// ===================
function initBaggagePage() {
  if (!state.booking) {
    window.location.href = 'index.html';
    return;
  }

  renderBaggageTabs();
  renderBaggageOptions(0);
  updateBaggageSummary();
}

function renderBaggageTabs() {
  const container = document.getElementById('baggage-tabs');
  if (!container) return;

  container.textContent = '';

  state.passengers.forEach((passenger, index) => {
    const tab = document.createElement('button');
    tab.className = `baggage-tab ${index === 0 ? 'active' : ''}`;
    tab.textContent = `${passenger.firstName} ${passenger.lastName}`;
    tab.onclick = () => selectBaggageTab(index);
    container.appendChild(tab);
  });
}

function selectBaggageTab(index) {
  document.querySelectorAll('.baggage-tab').forEach((tab, i) => {
    tab.classList.toggle('active', i === index);
  });
  renderBaggageOptions(index);
}

function renderBaggageOptions(passengerIndex) {
  const container = document.getElementById('baggage-options');
  if (!container) return;

  const passenger = state.passengers[passengerIndex];
  const currentBaggage = state.baggage[passenger.id] || 'carry-on';

  const options = [
    { id: 'carry-on', name: 'Carry-on Only', desc: '1 personal item + 1 carry-on bag', price: 0 },
    { id: 'one-bag', name: '1 Checked Bag', desc: 'Up to 50 lbs (23 kg)', price: 35 },
    { id: 'two-bags', name: '2 Checked Bags', desc: 'Up to 50 lbs each', price: 65 },
    { id: 'oversized', name: 'Oversized/Overweight', desc: 'Sports equipment, etc.', price: 100 }
  ];

  container.textContent = '';

  options.forEach(opt => {
    const label = document.createElement('label');
    label.className = 'baggage-option' + (currentBaggage === opt.id ? ' selected' : '');

    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'baggage-' + passengerIndex;
    input.value = opt.id;
    input.checked = currentBaggage === opt.id;
    input.addEventListener('change', () => selectBaggage(passengerIndex, opt.id, opt.price));

    const infoDiv = document.createElement('div');
    infoDiv.className = 'baggage-info';
    const h4 = document.createElement('h4');
    h4.textContent = opt.name;
    const p = document.createElement('p');
    p.textContent = opt.desc;
    infoDiv.appendChild(h4);
    infoDiv.appendChild(p);

    const priceSpan = document.createElement('span');
    priceSpan.className = 'baggage-price';
    priceSpan.textContent = opt.price === 0 ? 'Included' : '$' + opt.price;

    label.appendChild(input);
    label.appendChild(infoDiv);
    label.appendChild(priceSpan);
    container.appendChild(label);
  });
}

function selectBaggage(passengerIndex, optionId, price) {
  const passenger = state.passengers[passengerIndex];
  state.baggage[passenger.id] = optionId;
  if (!state.baggagePrices) state.baggagePrices = {};
  state.baggagePrices[passenger.id] = price;
  saveState();

  renderBaggageOptions(passengerIndex);
  updateBaggageSummary();
}

function updateBaggageSummary() {
  const container = document.getElementById('baggage-summary-items');
  if (!container) return;

  container.textContent = '';
  let total = 0;

  const optionNames = {
    'carry-on': 'Carry-on Only',
    'one-bag': '1 Checked Bag',
    'two-bags': '2 Checked Bags',
    'oversized': 'Oversized'
  };

  state.passengers.forEach(passenger => {
    const option = state.baggage[passenger.id] || 'carry-on';
    const price = state.baggagePrices?.[passenger.id] || 0;
    total += price;

    const item = document.createElement('div');
    item.className = 'summary-item';

    const nameSpan = document.createElement('span');
    nameSpan.textContent = passenger.firstName + ': ' + optionNames[option];

    const priceSpan = document.createElement('span');
    priceSpan.textContent = price === 0 ? 'Included' : '$' + price;

    item.appendChild(nameSpan);
    item.appendChild(priceSpan);
    container.appendChild(item);
  });

  document.getElementById('baggage-total').textContent = '$' + total;
}

// ===================
// REVIEW PAGE
// ===================
function initReviewPage() {
  if (!state.booking) {
    window.location.href = 'index.html';
    return;
  }

  renderReviewSummary();
  initTermsScroll();
}

function renderReviewSummary() {
  // Helper function to create a review row
  function createReviewRow(label, value) {
    const row = document.createElement('div');
    row.className = 'review-row';

    const labelSpan = document.createElement('span');
    labelSpan.className = 'review-label';
    labelSpan.textContent = label;

    const valueSpan = document.createElement('span');
    valueSpan.className = 'review-value';
    valueSpan.textContent = value;

    row.appendChild(labelSpan);
    row.appendChild(valueSpan);
    return row;
  }

  // Flight info
  const flightSection = document.getElementById('review-flight');
  if (flightSection) {
    flightSection.textContent = '';

    flightSection.appendChild(createReviewRow('Flight', state.booking.flight.number));
    flightSection.appendChild(createReviewRow('Route', state.booking.flight.origin + ' → ' + state.booking.flight.destination));
    flightSection.appendChild(createReviewRow('Date', state.booking.flight.date));
    flightSection.appendChild(createReviewRow('Time', state.booking.flight.time));
  }

  // Passengers
  const passengersSection = document.getElementById('review-passengers');
  if (passengersSection) {
    passengersSection.textContent = '';

    state.passengers.forEach(p => {
      const seatValue = 'Seat ' + (state.seats[p.id] || 'Not selected');
      passengersSection.appendChild(createReviewRow(p.firstName + ' ' + p.lastName, seatValue));
    });
  }

  // Calculate totals
  let seatTotal = Object.values(state.seatPrices || {}).reduce((a, b) => a + b, 0);
  let baggageTotal = Object.values(state.baggagePrices || {}).reduce((a, b) => a + b, 0);
  let promoTotal = state.promoAccepted ? 99 * state.passengers.length : 0;
  let grandTotal = seatTotal + baggageTotal + promoTotal;

  document.getElementById('total-amount').textContent = `$${grandTotal}`;
}

function initTermsScroll() {
  const termsBox = document.querySelector('.terms-box');
  const checkbox = document.getElementById('terms-checkbox');
  const scrollHint = document.querySelector('.scroll-hint');
  const checkboxHint = document.querySelector('.checkbox-hint');

  if (!termsBox || !checkbox) return;

  termsBox.addEventListener('scroll', () => {
    const isAtBottom = termsBox.scrollHeight - termsBox.scrollTop <= termsBox.clientHeight + 10;

    if (isAtBottom) {
      state.termsRead = true;
      scrollHint?.classList.add('hidden');
      checkboxHint?.classList.add('hidden');
    }
  });

  checkbox.addEventListener('change', () => {
    if (!state.termsRead) {
      checkbox.checked = false;
      alert('Please scroll through and read the terms and conditions first.');
      return;
    }
    state.termsAccepted = checkbox.checked;
    document.getElementById('confirm-btn').disabled = !checkbox.checked;
  });
}

function handleConfirm() {
  if (!state.termsAccepted) {
    alert('Please accept the terms and conditions to continue.');
    return;
  }

  // Show confirmation modal
  document.getElementById('confirm-modal').classList.add('active');
}

function closeConfirmModal() {
  document.getElementById('confirm-modal').classList.remove('active');
}

function finalConfirm() {
  saveState();
  window.location.href = 'success.html';
}

// ===================
// SUCCESS PAGE
// ===================
function initSuccessPage() {
  if (!state.booking) {
    window.location.href = 'index.html';
    return;
  }

  renderBoardingPasses();
}

function renderBoardingPasses() {
  const container = document.getElementById('boarding-passes');
  if (!container) return;

  container.textContent = '';

  state.passengers.forEach(passenger => {
    const card = document.createElement('div');
    card.className = 'boarding-pass';

    // Header
    const header = document.createElement('div');
    header.className = 'bp-header';
    const airlineSpan = document.createElement('span');
    airlineSpan.textContent = 'AnyCompany Popups';
    const flightSpan = document.createElement('span');
    flightSpan.textContent = state.booking.flight.number;
    header.appendChild(airlineSpan);
    header.appendChild(flightSpan);

    // Body
    const body = document.createElement('div');
    body.className = 'bp-body';

    // Route
    const route = document.createElement('div');
    route.className = 'bp-route';

    // Origin city
    const originCity = document.createElement('div');
    originCity.className = 'bp-city';
    const originCode = document.createElement('div');
    originCode.className = 'bp-code';
    originCode.textContent = state.booking.flight.origin;
    const originName = document.createElement('div');
    originName.className = 'bp-name';
    originName.textContent = state.booking.flight.originCity;
    originCity.appendChild(originCode);
    originCity.appendChild(originName);

    // Arrow
    const arrow = document.createElement('div');
    arrow.className = 'bp-arrow';
    arrow.textContent = '✈️';

    // Destination city
    const destCity = document.createElement('div');
    destCity.className = 'bp-city';
    const destCode = document.createElement('div');
    destCode.className = 'bp-code';
    destCode.textContent = state.booking.flight.destination;
    const destName = document.createElement('div');
    destName.className = 'bp-name';
    destName.textContent = state.booking.flight.destinationCity;
    destCity.appendChild(destCode);
    destCity.appendChild(destName);

    route.appendChild(originCity);
    route.appendChild(arrow);
    route.appendChild(destCity);

    // Passenger name
    const passengerDiv = document.createElement('div');
    passengerDiv.className = 'bp-passenger';
    passengerDiv.textContent = passenger.firstName + ' ' + passenger.lastName;

    // Details
    const details = document.createElement('div');
    details.className = 'bp-details';

    const detailItems = [
      { label: 'Date', value: state.booking.flight.date },
      { label: 'Boarding', value: '07:45' },
      { label: 'Seat', value: state.seats[passenger.id] || 'N/A' },
      { label: 'Gate', value: 'B12' }
    ];

    detailItems.forEach(item => {
      const detailDiv = document.createElement('div');
      const labelDiv = document.createElement('div');
      labelDiv.className = 'bp-label';
      labelDiv.textContent = item.label;
      const valueDiv = document.createElement('div');
      valueDiv.className = 'bp-value';
      valueDiv.textContent = item.value;
      detailDiv.appendChild(labelDiv);
      detailDiv.appendChild(valueDiv);
      details.appendChild(detailDiv);
    });

    body.appendChild(route);
    body.appendChild(passengerDiv);
    body.appendChild(details);

    card.appendChild(header);
    card.appendChild(body);
    container.appendChild(card);
  });
}

function downloadBoardingPasses() {
  const f = state.booking.flight;
  let content = `PACIFICSKY AIRWAYS - BOARDING PASSES
${'='.repeat(50)}
Confirmation: ${state.booking.confirmationCode}
Flight: ${f.number}
Route: ${f.origin} (${f.originCity}) → ${f.destination} (${f.destinationCity})
Date: ${f.date}
Departure: ${f.time}
Aircraft: ${f.aircraft}
${'='.repeat(50)}

`;

  state.passengers.forEach(p => {
    const seat = state.seats[p.id];
    content += `
PASSENGER: ${p.firstName} ${p.lastName}
Seat: ${seat || 'Not assigned'}
Gate: B12
Boarding Time: 07:45
${'-'.repeat(50)}
`;
  });

  content += `
*** PLEASE ARRIVE AT THE GATE AT LEAST 30 MINUTES BEFORE DEPARTURE ***
*** MAHALO FOR FLYING PACIFICSKY AIRWAYS ***
`;

  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `boarding-passes-${state.booking.confirmationCode}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function emailBoardingPasses() {
  alert('Boarding passes have been sent to your email.');
}

function newCheckIn() {
  // Clear session and start over
  sessionStorage.removeItem('pacificsky_state');
  sessionStorage.removeItem('promo_dismissed');
  window.location.href = 'index.html';
}

// ===================
// NAVIGATION
// ===================
function handleContinue() {
  saveState();

  switch (state.currentPage) {
    case 'passengers':
      window.location.href = 'seats.html';
      break;
    case 'seats':
      window.location.href = 'baggage.html';
      break;
    case 'baggage':
      window.location.href = 'review.html';
      break;
  }
}
