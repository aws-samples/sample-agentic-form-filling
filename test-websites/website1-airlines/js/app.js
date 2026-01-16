// AnyCompany Airlines - Check-in Application

const BOOKING_DATA = {
  confirmation: "SKW789",
  lastName: "Stiles",
  flight: {
    number: "SW1234",
    airline: "AnyCompany Airlines",
    departure: { airport: "JFK", city: "New York", terminal: "4", gate: "B22", date: "2025-01-15", time: "08:30" },
    arrival: { airport: "LAX", city: "Los Angeles", terminal: "6", date: "2025-01-15", time: "11:45" },
    aircraft: "AnyPlane 700",
    duration: "5h 15m"
  },
  passengers: [
    { id: 1, firstName: "John", lastName: "Stiles", type: "adult" },
    { id: 2, firstName: "Mary", lastName: "Stiles", type: "adult" },
    { id: 3, firstName: "Mateo", lastName: "Stiles", type: "child" }
  ],
  seatMap: {
    rows: 30,
    columns: ["A", "B", "C", "D", "E", "F"],
    premiumRows: [1, 2, 3, 4, 5],
    exitRows: [10, 25],
    occupied: ["1A", "1B", "2C", "2D", "3A", "4F", "5B", "5C", "6A", "6D", "7B", "7E", "8A", "8C", "8F", "9B", "10A", "10D", "11C", "11E", "12A", "12B", "13D", "13F", "14A", "14E", "15B", "15C", "16A", "16F", "17D", "18B", "18E", "19A", "19C", "20D", "20F", "21A", "21B", "22C", "22E", "23A", "23F", "24B", "24D", "25A", "25C", "25E", "26B", "26F", "27A", "27D", "28C", "28E", "29A", "29B", "30D", "30F"],
    premiumPrice: 25
  },
  baggage: {
    included: { cabin: 1, checked: 1 },
    options: [
      { id: "extra-cabin", name: "Extra Cabin Bag", price: 35 },
      { id: "extra-checked", name: "Extra Checked Bag", price: 45 },
      { id: "overweight", name: "Overweight Bag (23-32kg)", price: 75 }
    ]
  },
  extras: [
    { id: "insurance", name: "Travel Insurance", price: 29, description: "Trip cancellation and medical coverage" },
    { id: "lounge", name: "Lounge Access", price: 45, description: "Pre-flight lounge access at JFK" },
    { id: "priority", name: "Priority Boarding", price: 15, description: "Board first and secure overhead space" },
    { id: "wifi", name: "In-flight WiFi", price: 12, description: "High-speed internet during flight" },
    { id: "meal", name: "Premium Meal", price: 18, description: "Chef-prepared meal selection" }
  ]
};

// State management
const state = {
  currentPassenger: 0,
  passengerSeats: {},
  passengerBaggage: {},
  extras: [],
  validated: false
};

// XSS Protection: Escape HTML special characters
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
}

// Initialize state from localStorage if available
function loadState() {
  const saved = localStorage.getItem('skywest-checkin');
  if (saved) {
    const parsed = JSON.parse(saved);
    // Whitelist allowed state properties to prevent mass assignment vulnerabilities
    const allowedKeys = ['currentPassenger', 'passengerSeats', 'passengerBaggage', 'extras', 'validated'];
    const sanitizedData = Object.fromEntries(
      Object.entries(parsed).filter(([key]) => allowedKeys.includes(key))
    );
    Object.assign(state, sanitizedData);
  }
}

function saveState() {
  localStorage.setItem('skywest-checkin', JSON.stringify(state));
}

function clearState() {
  localStorage.removeItem('skywest-checkin');
}

// Login validation
function validateLogin(event) {
  event.preventDefault();

  const code = document.getElementById('confirmation-code').value.toUpperCase();
  const lastName = document.getElementById('last-name').value.trim();

  const codeError = document.getElementById('code-error');
  const nameError = document.getElementById('name-error');

  codeError.textContent = '';
  nameError.textContent = '';

  let valid = true;

  if (code !== BOOKING_DATA.confirmation) {
    codeError.textContent = 'Invalid confirmation code';
    valid = false;
  }

  if (lastName.toLowerCase() !== BOOKING_DATA.lastName.toLowerCase()) {
    nameError.textContent = 'Last name does not match booking';
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

// Seat Map Functions
function initSeatMap() {
  loadState();

  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderPassengerTabs();
  renderSeatMap();
  updateContinueButton();
}

function renderPassengerTabs() {
  const container = document.getElementById('passenger-tabs');
  if (!container) return;

  container.textContent = '';
  BOOKING_DATA.passengers.forEach((p, idx) => {
    const seat = state.passengerSeats[p.id] || null;
    const isActive = idx === state.currentPassenger;
    const hasSeat = seat !== null;

    const button = document.createElement('button');
    button.className = `passenger-tab ${isActive ? 'active' : ''} ${hasSeat ? 'has-seat' : ''}`;
    button.onclick = () => selectPassenger(idx);
    button.setAttribute('aria-label', `Select seat for ${escapeHtml(p.firstName)} ${escapeHtml(p.lastName)}`);

    const nameDiv = document.createElement('div');
    nameDiv.className = 'name';
    nameDiv.textContent = p.firstName;

    const seatDiv = document.createElement('div');
    seatDiv.className = 'seat';
    seatDiv.textContent = hasSeat ? 'Seat ' + seat : 'No seat';

    button.appendChild(nameDiv);
    button.appendChild(seatDiv);
    container.appendChild(button);
  });
}

function selectPassenger(idx) {
  state.currentPassenger = idx;
  saveState();
  renderPassengerTabs();
  renderSeatMap();
}

function renderSeatMap() {
  const container = document.getElementById('seat-grid');
  if (!container) return;

  container.textContent = '';
  const { rows, columns, premiumRows, exitRows, occupied } = BOOKING_DATA.seatMap;
  const selectedSeats = Object.values(state.passengerSeats);
  const currentPassengerId = BOOKING_DATA.passengers[state.currentPassenger].id;
  const currentSeat = state.passengerSeats[currentPassengerId];

  // Column labels
  const columnLabels = document.createElement('div');
  columnLabels.className = 'column-labels';
  const emptyRowNum = document.createElement('span');
  emptyRowNum.className = 'row-number';
  columnLabels.appendChild(emptyRowNum);

  columns.forEach((col, idx) => {
    const label = document.createElement('span');
    label.className = 'column-label';
    label.textContent = col;
    columnLabels.appendChild(label);
    if (idx === 2) {
      const aisle = document.createElement('span');
      aisle.className = 'aisle';
      columnLabels.appendChild(aisle);
    }
  });
  container.appendChild(columnLabels);

  // Seat rows
  for (let row = 1; row <= rows; row++) {
    const rowDiv = document.createElement('div');
    rowDiv.className = 'seat-row';
    rowDiv.dataset.row = row;

    const rowNum = document.createElement('span');
    rowNum.className = 'row-number';
    rowNum.textContent = row;
    rowDiv.appendChild(rowNum);

    columns.forEach((col, idx) => {
      const seatId = `${row}${col}`;
      const isOccupied = occupied.includes(seatId);
      const isSelectedByOther = selectedSeats.includes(seatId) && state.passengerSeats[currentPassengerId] !== seatId;
      const isCurrentSeat = currentSeat === seatId;
      const isPremium = premiumRows.includes(row);
      const isExit = exitRows.includes(row);

      const classes = ['seat'];
      if (isOccupied || isSelectedByOther) {
        classes.push('occupied');
      } else if (isCurrentSeat) {
        classes.push('selected');
      } else {
        classes.push('available');
        if (isPremium) classes.push('premium');
      }
      if (isExit) classes.push('exit');

      const clickable = !isOccupied && !isSelectedByOther;

      const button = document.createElement('button');
      button.className = classes.join(' ');
      button.dataset.seat = seatId;
      button.disabled = !clickable;
      if (clickable) {
        button.onclick = () => selectSeat(seatId);
      }
      button.setAttribute('aria-label', `Seat ${escapeHtml(seatId)}${isPremium ? ' Premium' : ''}${isExit ? ' Exit Row' : ''}${isOccupied ? ' Occupied' : ''}`);
      button.textContent = col;
      rowDiv.appendChild(button);

      if (idx === 2) {
        const aisle = document.createElement('span');
        aisle.className = 'aisle';
        rowDiv.appendChild(aisle);
      }
    });

    container.appendChild(rowDiv);
  }
}

function selectSeat(seatId) {
  const currentPassengerId = BOOKING_DATA.passengers[state.currentPassenger].id;

  // Toggle seat selection
  if (state.passengerSeats[currentPassengerId] === seatId) {
    delete state.passengerSeats[currentPassengerId];
  } else {
    state.passengerSeats[currentPassengerId] = seatId;
  }

  saveState();
  renderPassengerTabs();
  renderSeatMap();
  updateContinueButton();
}

function updateContinueButton() {
  const btn = document.getElementById('continue-btn');
  if (!btn) return;

  const allSeatsSelected = BOOKING_DATA.passengers.every(p => state.passengerSeats[p.id]);
  btn.disabled = !allSeatsSelected;
}

function goToSeats() {
  window.location.href = 'seats.html';
}

function goToBaggage() {
  saveState();
  window.location.href = 'baggage.html';
}

// Baggage Functions
function initBaggage() {
  loadState();

  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderBaggageOptions();
}

function renderBaggageOptions() {
  const container = document.getElementById('baggage-options');
  if (!container) return;

  // Initialize baggage state for each passenger
  BOOKING_DATA.passengers.forEach(p => {
    if (!state.passengerBaggage[p.id]) {
      state.passengerBaggage[p.id] = [];
    }
  });

  container.textContent = '';

  BOOKING_DATA.passengers.forEach(p => {
    const card = document.createElement('div');
    card.className = 'card';

    const cardTitle = document.createElement('h3');
    cardTitle.className = 'card-title';
    cardTitle.textContent = `${p.firstName} ${p.lastName}`;
    card.appendChild(cardTitle);

    const includedBaggage = document.createElement('div');
    includedBaggage.className = 'included-baggage';
    const includedP = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = 'Included:';
    includedP.appendChild(strong);
    includedP.appendChild(document.createTextNode(` ${BOOKING_DATA.baggage.included.cabin} cabin bag, ${BOOKING_DATA.baggage.included.checked} checked bag`));
    includedBaggage.appendChild(includedP);
    card.appendChild(includedBaggage);

    const optionGrid = document.createElement('div');
    optionGrid.className = 'option-grid';

    BOOKING_DATA.baggage.options.forEach(opt => {
      const isSelected = state.passengerBaggage[p.id].includes(opt.id);

      const label = document.createElement('label');
      label.className = `option-card ${isSelected ? 'selected' : ''}`;

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
      label.appendChild(optionInfo);

      const optionPrice = document.createElement('div');
      optionPrice.className = 'option-price';
      optionPrice.textContent = `+$${opt.price}`;
      label.appendChild(optionPrice);

      optionGrid.appendChild(label);
    });

    card.appendChild(optionGrid);
    container.appendChild(card);
  });
}

function toggleBaggage(passengerId, optionId) {
  const baggage = state.passengerBaggage[passengerId] || [];
  const idx = baggage.indexOf(optionId);

  if (idx === -1) {
    baggage.push(optionId);
  } else {
    baggage.splice(idx, 1);
  }

  state.passengerBaggage[passengerId] = baggage;
  saveState();
  renderBaggageOptions();
}

function goToExtras() {
  saveState();
  window.location.href = 'extras.html';
}

// Extras Functions
function initExtras() {
  loadState();

  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderExtrasOptions();
}

function renderExtrasOptions() {
  const container = document.getElementById('extras-options');
  if (!container) return;

  container.textContent = '';

  BOOKING_DATA.extras.forEach(opt => {
    const isSelected = state.extras.includes(opt.id);

    const label = document.createElement('label');
    label.className = `option-card ${isSelected ? 'selected' : ''}`;

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
    optionDesc.className = 'option-description';
    optionDesc.textContent = opt.description;
    optionInfo.appendChild(optionDesc);

    label.appendChild(optionInfo);

    const optionPrice = document.createElement('div');
    optionPrice.className = 'option-price';
    optionPrice.textContent = `+$${opt.price}`;
    label.appendChild(optionPrice);

    container.appendChild(label);
  });
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

function goToReview() {
  saveState();
  window.location.href = 'review.html';
}

// Review Functions
function initReview() {
  loadState();

  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderReview();
}

// Helper to create table row with header and data
function createTableRow(headerText, dataText) {
  const tr = document.createElement('tr');
  const th = document.createElement('th');
  th.textContent = headerText;
  const td = document.createElement('td');
  td.textContent = dataText;
  tr.appendChild(th);
  tr.appendChild(td);
  return tr;
}

function renderReview() {
  // Flight info
  const flightInfo = document.getElementById('flight-info');
  if (flightInfo) {
    const f = BOOKING_DATA.flight;
    flightInfo.textContent = '';

    const table = document.createElement('table');
    table.className = 'review-table';

    table.appendChild(createTableRow('Flight', f.number));
    table.appendChild(createTableRow('Route', `${f.departure.airport} → ${f.arrival.airport}`));
    table.appendChild(createTableRow('Date', f.departure.date));
    table.appendChild(createTableRow('Departure', f.departure.time));
    table.appendChild(createTableRow('Aircraft', f.aircraft));

    flightInfo.appendChild(table);
  }

  // Passengers & Seats
  const passengersInfo = document.getElementById('passengers-info');
  if (passengersInfo) {
    let seatCost = 0;
    passengersInfo.textContent = '';

    const passTable = document.createElement('table');
    passTable.className = 'review-table';

    const headerRow = document.createElement('tr');
    ['Passenger', 'Seat', 'Cost'].forEach(text => {
      const th = document.createElement('th');
      th.textContent = text;
      headerRow.appendChild(th);
    });
    passTable.appendChild(headerRow);

    BOOKING_DATA.passengers.forEach(p => {
      const seat = state.passengerSeats[p.id];
      const row = parseInt(seat);
      const isPremium = BOOKING_DATA.seatMap.premiumRows.includes(row);
      const cost = isPremium ? BOOKING_DATA.seatMap.premiumPrice : 0;
      seatCost += cost;

      const tr = document.createElement('tr');
      const tdName = document.createElement('td');
      tdName.textContent = `${p.firstName} ${p.lastName}`;
      const tdSeat = document.createElement('td');
      tdSeat.textContent = seat;
      const tdCost = document.createElement('td');
      tdCost.textContent = cost > 0 ? '$' + cost : 'Free';
      tr.appendChild(tdName);
      tr.appendChild(tdSeat);
      tr.appendChild(tdCost);
      passTable.appendChild(tr);
    });

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row';
    const tdLabel = document.createElement('td');
    tdLabel.colSpan = 2;
    tdLabel.textContent = 'Seat Selection Total';
    const tdTotal = document.createElement('td');
    tdTotal.textContent = '$' + seatCost;
    totalRow.appendChild(tdLabel);
    totalRow.appendChild(tdTotal);
    passTable.appendChild(totalRow);

    passengersInfo.appendChild(passTable);
  }

  // Baggage
  const baggageInfo = document.getElementById('baggage-info');
  if (baggageInfo) {
    let baggageCost = 0;
    baggageInfo.textContent = '';

    const bagTable = document.createElement('table');
    bagTable.className = 'review-table';

    const bagHeaderRow = document.createElement('tr');
    ['Passenger', 'Item', 'Cost'].forEach(text => {
      const th = document.createElement('th');
      th.textContent = text;
      bagHeaderRow.appendChild(th);
    });
    bagTable.appendChild(bagHeaderRow);

    let hasBaggage = false;
    BOOKING_DATA.passengers.forEach(p => {
      const bags = state.passengerBaggage[p.id] || [];
      bags.forEach(bagId => {
        const opt = BOOKING_DATA.baggage.options.find(o => o.id === bagId);
        if (opt) {
          hasBaggage = true;
          baggageCost += opt.price;
          const tr = document.createElement('tr');
          const tdPassenger = document.createElement('td');
          tdPassenger.textContent = p.firstName;
          const tdItem = document.createElement('td');
          tdItem.textContent = opt.name;
          const tdPrice = document.createElement('td');
          tdPrice.textContent = '$' + opt.price;
          tr.appendChild(tdPassenger);
          tr.appendChild(tdItem);
          tr.appendChild(tdPrice);
          bagTable.appendChild(tr);
        }
      });
    });

    if (!hasBaggage) {
      const emptyRow = document.createElement('tr');
      const emptyTd = document.createElement('td');
      emptyTd.colSpan = 3;
      emptyTd.textContent = 'No extra baggage selected';
      emptyRow.appendChild(emptyTd);
      bagTable.appendChild(emptyRow);
    }

    const bagTotalRow = document.createElement('tr');
    bagTotalRow.className = 'total-row';
    const bagTotalLabel = document.createElement('td');
    bagTotalLabel.colSpan = 2;
    bagTotalLabel.textContent = 'Baggage Total';
    const bagTotalValue = document.createElement('td');
    bagTotalValue.textContent = '$' + baggageCost;
    bagTotalRow.appendChild(bagTotalLabel);
    bagTotalRow.appendChild(bagTotalValue);
    bagTable.appendChild(bagTotalRow);

    baggageInfo.appendChild(bagTable);
  }

  // Extras
  const extrasInfo = document.getElementById('extras-info');
  if (extrasInfo) {
    let extrasCost = 0;
    extrasInfo.textContent = '';

    const extTable = document.createElement('table');
    extTable.className = 'review-table';

    const extHeaderRow = document.createElement('tr');
    ['Extra', 'Cost'].forEach(text => {
      const th = document.createElement('th');
      th.textContent = text;
      extHeaderRow.appendChild(th);
    });
    extTable.appendChild(extHeaderRow);

    let hasExtras = false;
    state.extras.forEach(extId => {
      const opt = BOOKING_DATA.extras.find(o => o.id === extId);
      if (opt) {
        hasExtras = true;
        extrasCost += opt.price;
        const tr = document.createElement('tr');
        const tdName = document.createElement('td');
        tdName.textContent = opt.name;
        const tdPrice = document.createElement('td');
        tdPrice.textContent = '$' + opt.price;
        tr.appendChild(tdName);
        tr.appendChild(tdPrice);
        extTable.appendChild(tr);
      }
    });

    if (!hasExtras) {
      const emptyRow = document.createElement('tr');
      const emptyTd = document.createElement('td');
      emptyTd.colSpan = 2;
      emptyTd.textContent = 'No extras selected';
      emptyRow.appendChild(emptyTd);
      extTable.appendChild(emptyRow);
    }

    const extTotalRow = document.createElement('tr');
    extTotalRow.className = 'total-row';
    const extTotalLabel = document.createElement('td');
    extTotalLabel.textContent = 'Extras Total';
    const extTotalValue = document.createElement('td');
    extTotalValue.textContent = '$' + extrasCost;
    extTotalRow.appendChild(extTotalLabel);
    extTotalRow.appendChild(extTotalValue);
    extTable.appendChild(extTotalRow);

    extrasInfo.appendChild(extTable);
  }

  // Calculate grand total
  const totalElement = document.getElementById('grand-total');
  if (totalElement) {
    let total = 0;

    // Seat costs
    BOOKING_DATA.passengers.forEach(p => {
      const seat = state.passengerSeats[p.id];
      if (seat) {
        const row = parseInt(seat);
        if (BOOKING_DATA.seatMap.premiumRows.includes(row)) {
          total += BOOKING_DATA.seatMap.premiumPrice;
        }
      }
    });

    // Baggage costs
    BOOKING_DATA.passengers.forEach(p => {
      const bags = state.passengerBaggage[p.id] || [];
      bags.forEach(bagId => {
        const opt = BOOKING_DATA.baggage.options.find(o => o.id === bagId);
        if (opt) total += opt.price;
      });
    });

    // Extras costs
    state.extras.forEach(extId => {
      const opt = BOOKING_DATA.extras.find(o => o.id === extId);
      if (opt) total += opt.price;
    });

    totalElement.textContent = `$${total}`;
  }
}

function confirmCheckIn() {
  saveState();
  window.location.href = 'success.html';
}

// Success Functions
function initSuccess() {
  loadState();

  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderBoardingPasses();
}

function renderBoardingPasses() {
  const container = document.getElementById('boarding-passes');
  if (!container) return;

  const f = BOOKING_DATA.flight;
  container.textContent = '';

  BOOKING_DATA.passengers.forEach(p => {
    const seat = state.passengerSeats[p.id];

    const boardingPass = document.createElement('div');
    boardingPass.className = 'boarding-pass';

    // Header
    const header = document.createElement('div');
    header.className = 'boarding-pass-header';
    const logo = document.createElement('div');
    logo.className = 'logo';
    logo.textContent = BOOKING_DATA.flight.airline;
    const flightNum = document.createElement('div');
    flightNum.className = 'flight-number';
    flightNum.textContent = 'Flight ' + f.number;
    header.appendChild(logo);
    header.appendChild(flightNum);
    boardingPass.appendChild(header);

    // Route
    const route = document.createElement('div');
    route.className = 'boarding-pass-route';

    const depCity = document.createElement('div');
    depCity.className = 'boarding-pass-city';
    const depCode = document.createElement('div');
    depCode.className = 'boarding-pass-code';
    depCode.textContent = f.departure.airport;
    const depName = document.createElement('div');
    depName.className = 'boarding-pass-name';
    depName.textContent = f.departure.city;
    depCity.appendChild(depCode);
    depCity.appendChild(depName);

    const arrow = document.createElement('div');
    arrow.className = 'boarding-pass-arrow';
    arrow.textContent = '→';

    const arrCity = document.createElement('div');
    arrCity.className = 'boarding-pass-city';
    const arrCode = document.createElement('div');
    arrCode.className = 'boarding-pass-code';
    arrCode.textContent = f.arrival.airport;
    const arrName = document.createElement('div');
    arrName.className = 'boarding-pass-name';
    arrName.textContent = f.arrival.city;
    arrCity.appendChild(arrCode);
    arrCity.appendChild(arrName);

    route.appendChild(depCity);
    route.appendChild(arrow);
    route.appendChild(arrCity);
    boardingPass.appendChild(route);

    // Passenger name
    const passengerName = document.createElement('div');
    passengerName.style.cssText = 'font-size: 1.25rem; font-weight: 600; text-align: center; margin: 1rem 0;';
    passengerName.textContent = p.firstName + ' ' + p.lastName;
    boardingPass.appendChild(passengerName);

    // Details
    const details = document.createElement('div');
    details.className = 'boarding-pass-details';

    const detailItems = [
      { label: 'Date', value: f.departure.date },
      { label: 'Boarding', value: f.departure.time },
      { label: 'Gate', value: f.departure.gate },
      { label: 'Seat', value: seat }
    ];

    detailItems.forEach(item => {
      const detailItem = document.createElement('div');
      detailItem.className = 'detail-item';
      const detailLabel = document.createElement('div');
      detailLabel.className = 'detail-label';
      detailLabel.textContent = item.label;
      const detailValue = document.createElement('div');
      detailValue.className = 'detail-value';
      detailValue.textContent = item.value;
      detailItem.appendChild(detailLabel);
      detailItem.appendChild(detailValue);
      details.appendChild(detailItem);
    });

    boardingPass.appendChild(details);

    // QR Code
    const qrCode = document.createElement('div');
    qrCode.className = 'qr-code';
    qrCode.textContent = '[QR Code]';
    boardingPass.appendChild(qrCode);

    // Notice
    const notice = document.createElement('p');
    notice.style.cssText = 'text-align: center; color: var(--gray-500); font-size: 0.85rem;';
    notice.textContent = 'Please arrive at the gate at least 30 minutes before departure';
    boardingPass.appendChild(notice);

    container.appendChild(boardingPass);
  });
}

function downloadBoardingPasses() {
  const f = BOOKING_DATA.flight;
  let content = `SKYWEST AIRLINES - BOARDING PASSES
${'='.repeat(50)}
Confirmation: ${BOOKING_DATA.confirmation}
Flight: ${f.number}
Route: ${f.departure.airport} (${f.departure.city}) → ${f.arrival.airport} (${f.arrival.city})
Date: ${f.departure.date}
Departure: ${f.departure.time}
Aircraft: ${f.aircraft}
${'='.repeat(50)}

`;

  BOOKING_DATA.passengers.forEach(p => {
    const seat = state.passengerSeats[p.id];
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
  a.download = `boarding-passes-${BOOKING_DATA.confirmation}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function startNewCheckIn() {
  clearState();
  window.location.href = 'index.html';
}

// Initialize based on current page
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;

  switch (page) {
    case 'login':
      // Login page - no init needed
      break;
    case 'seats':
      initSeatMap();
      break;
    case 'baggage':
      initBaggage();
      break;
    case 'extras':
      initExtras();
      break;
    case 'review':
      initReview();
      break;
    case 'success':
      initSuccess();
      break;
  }
});
