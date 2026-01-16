// AnyCompany SeatMap - Minimal Check-in Application

const BOOKING = {
  confirmation: "QF456",
  lastName: "García",
  flight: {
    number: "QF567",
    departure: { airport: "ORD", city: "Chicago O'Hare", date: "2025-01-20", time: "14:15", gate: "C12", terminal: "2" },
    arrival: { airport: "MIA", city: "Miami", date: "2025-01-20", time: "18:30" },
    aircraft: "AnyPlane 320",
    duration: "3h 15m"
  },
  passenger: { firstName: "María", lastName: "García" },
  seatMap: {
    rows: 30,
    columns: ["A", "B", "C", "D", "E", "F"],
    exitRows: [10, 11, 25, 26],
    bulkheadRows: [1, 12],
    premiumRows: [1, 2, 3, 4, 5],
    premiumPrice: 40,
    exitPrice: 40
  },
  baggage: {
    included: "1 cabin bag (8kg), 1 checked bag (23kg)",
    options: [
      { id: "extra-cabin", name: "Extra Cabin Bag", price: 30 },
      { id: "extra-checked", name: "Extra Checked Bag (23kg)", price: 40 },
      { id: "heavy-checked", name: "Heavy Checked Bag (32kg)", price: 60 },
      { id: "sports", name: "Sports Equipment", price: 50 }
    ]
  }
};

// Generate random occupied seats (40% occupied)
function generateOccupiedSeats() {
  const stored = sessionStorage.getItem('qf-occupied');
  if (stored) return JSON.parse(stored);

  const occupied = [];
  const { rows, columns } = BOOKING.seatMap;

  for (let row = 1; row <= rows; row++) {
    for (const col of columns) {
      if (Math.random() < 0.4) {
        occupied.push(`${row}${col}`);
      }
    }
  }

  sessionStorage.setItem('qf-occupied', JSON.stringify(occupied));
  return occupied;
}

// State
const state = {
  validated: false,
  selectedSeat: null,
  baggage: [],
  occupiedSeats: []
};

// XSS Protection: Escape HTML special characters
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  const div = document.createElement('div');
  div.textContent = String(str);
  return div.innerHTML;
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

function loadState() {
  const saved = sessionStorage.getItem('qf-state');
  if (saved) {
    const parsed = JSON.parse(saved);
    // Whitelist allowed state properties to prevent mass assignment vulnerabilities
    const allowedKeys = ['validated', 'selectedSeat', 'baggage', 'occupiedSeats'];
    const sanitizedData = Object.fromEntries(
      Object.entries(parsed).filter(([key]) => allowedKeys.includes(key))
    );
    Object.assign(state, sanitizedData);
  }
  state.occupiedSeats = generateOccupiedSeats();
}

function saveState() {
  sessionStorage.setItem('qf-state', JSON.stringify(state));
}

function clearState() {
  sessionStorage.removeItem('qf-state');
  sessionStorage.removeItem('qf-occupied');
}

// Login
function validateLogin(event) {
  event.preventDefault();

  const code = document.getElementById('code').value.toUpperCase().trim();
  const name = document.getElementById('name').value.trim();

  document.getElementById('code-error').textContent = '';
  document.getElementById('name-error').textContent = '';

  let valid = true;

  if (code !== BOOKING.confirmation) {
    document.getElementById('code-error').textContent = 'Invalid confirmation code';
    valid = false;
  }

  if (name.toLowerCase() !== BOOKING.lastName.toLowerCase()) {
    document.getElementById('name-error').textContent = 'Last name does not match';
    valid = false;
  }

  if (valid) {
    clearState();
    state.validated = true;
    state.occupiedSeats = generateOccupiedSeats();
    saveState();
    window.location.href = 'seats.html';
  }

  return false;
}

// Seats
function initSeats() {
  loadState();
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderSeatMap();
  updateSelection();
}

function renderSeatMap() {
  const container = document.getElementById('seat-grid');
  if (!container) return;

  container.textContent = '';
  const { rows, columns, exitRows, bulkheadRows, premiumRows } = BOOKING.seatMap;

  // Column headers
  const columnHeaders = document.createElement('div');
  columnHeaders.className = 'column-headers';
  const emptySpan = document.createElement('span');
  columnHeaders.appendChild(emptySpan);
  columns.forEach((col, idx) => {
    const colSpan = document.createElement('span');
    colSpan.textContent = col;
    columnHeaders.appendChild(colSpan);
    if (idx === 2) {
      const aisleSpan = document.createElement('span');
      aisleSpan.className = 'aisle';
      columnHeaders.appendChild(aisleSpan);
    }
  });
  container.appendChild(columnHeaders);

  // Rows
  for (let row = 1; row <= rows; row++) {
    const isExit = exitRows.includes(row);
    const isBulkhead = bulkheadRows.includes(row);
    const isPremium = premiumRows.includes(row);

    const rowDiv = document.createElement('div');
    rowDiv.className = 'seat-row';
    rowDiv.dataset.row = row;

    const rowNum = document.createElement('span');
    rowNum.className = 'row-num';
    rowNum.textContent = row;
    rowDiv.appendChild(rowNum);

    columns.forEach((col, idx) => {
      const seatId = `${row}${col}`;
      const isOccupied = state.occupiedSeats.includes(seatId);
      const isSelected = state.selectedSeat === seatId;

      let classes = ['seat'];
      if (isOccupied) classes.push('occupied');
      else if (isSelected) classes.push('selected');
      if (isPremium && !isOccupied && !isSelected) classes.push('premium');
      if (isExit) classes.push('exit');
      if (isBulkhead) classes.push('bulkhead');

      const clickable = !isOccupied;
      const label = `Seat ${seatId}${isPremium ? ' Extra Legroom +$40' : ''}${isExit ? ' Exit Row' : ''}${isBulkhead ? ' Bulkhead' : ''}${isOccupied ? ' Unavailable' : ''}`;

      const button = document.createElement('button');
      button.className = classes.join(' ');
      button.dataset.seat = seatId;
      button.setAttribute('aria-label', label);
      button.setAttribute('title', label);
      button.textContent = col;
      if (clickable) {
        button.onclick = () => selectSeat(seatId);
      } else {
        button.disabled = true;
      }
      rowDiv.appendChild(button);

      if (idx === 2) {
        const aisleSpan = document.createElement('span');
        aisleSpan.className = 'aisle';
        rowDiv.appendChild(aisleSpan);
      }
    });

    // Row annotation
    if (isExit || isBulkhead) {
      const annotation = document.createElement('span');
      annotation.style.cssText = 'margin-left:10px;font-size:0.75em;color:#666;';
      annotation.textContent = isExit ? 'EXIT' : 'BULKHEAD';
      rowDiv.appendChild(annotation);
    }

    container.appendChild(rowDiv);
  }
}

function selectSeat(seatId) {
  state.selectedSeat = seatId;
  saveState();
  renderSeatMap();
  updateSelection();
}

function updateSelection() {
  const display = document.getElementById('selected-seat');
  const btn = document.getElementById('continue-btn');

  if (state.selectedSeat) {
    const row = parseInt(state.selectedSeat);
    const isPremium = BOOKING.seatMap.premiumRows.includes(row);
    const isExit = BOOKING.seatMap.exitRows.includes(row);
    const cost = (isPremium || isExit) ? '$40' : 'Free';

    display.textContent = `Selected: ${state.selectedSeat} (${cost})`;
    btn.disabled = false;
  } else {
    display.textContent = 'No seat selected';
    btn.disabled = true;
  }
}

function goToBaggage() {
  saveState();
  window.location.href = 'baggage.html';
}

// Baggage
function initBaggage() {
  loadState();
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderBaggage();
}

function renderBaggage() {
  const container = document.getElementById('baggage-options');
  if (!container) return;

  container.textContent = '';
  BOOKING.baggage.options.forEach(opt => {
    const checked = state.baggage.includes(opt.id);

    const li = document.createElement('li');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = opt.id;
    checkbox.checked = checked;
    checkbox.onchange = () => toggleBaggage(opt.id);
    li.appendChild(checkbox);

    const label = document.createElement('label');
    label.htmlFor = opt.id;
    label.textContent = opt.name;
    li.appendChild(label);

    const priceSpan = document.createElement('span');
    priceSpan.className = 'price';
    priceSpan.textContent = '+$' + opt.price;
    li.appendChild(priceSpan);

    container.appendChild(li);
  });
}

function toggleBaggage(optId) {
  const idx = state.baggage.indexOf(optId);
  if (idx === -1) {
    state.baggage.push(optId);
  } else {
    state.baggage.splice(idx, 1);
  }
  saveState();
}

function goToReview() {
  saveState();
  window.location.href = 'review.html';
}

// Review
function initReview() {
  loadState();
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderReview();
}

function renderReview() {
  const f = BOOKING.flight;
  const p = BOOKING.passenger;

  // Flight
  const flightInfo = document.getElementById('flight-info');
  if (flightInfo) {
    flightInfo.textContent = '';
    const flightTable = document.createElement('table');
    flightTable.appendChild(createTableRow('Flight', f.number));
    flightTable.appendChild(createTableRow('Route', f.departure.airport + ' to ' + f.arrival.airport));
    flightTable.appendChild(createTableRow('Date', f.departure.date));
    flightTable.appendChild(createTableRow('Departure', f.departure.time));
    flightTable.appendChild(createTableRow('Aircraft', f.aircraft));
    flightInfo.appendChild(flightTable);
  }

  // Passenger
  const row = parseInt(state.selectedSeat);
  const isPremium = BOOKING.seatMap.premiumRows.includes(row);
  const isExit = BOOKING.seatMap.exitRows.includes(row);
  const seatCost = (isPremium || isExit) ? 40 : 0;

  const passengerInfo = document.getElementById('passenger-info');
  if (passengerInfo) {
    passengerInfo.textContent = '';
    const passTable = document.createElement('table');
    passTable.appendChild(createTableRow('Passenger', p.firstName + ' ' + p.lastName));

    let seatText = state.selectedSeat;
    if (isPremium) seatText += ' (Extra Legroom)';
    if (isExit) seatText += ' (Exit Row)';
    passTable.appendChild(createTableRow('Seat', seatText));
    passTable.appendChild(createTableRow('Seat Cost', seatCost > 0 ? '$' + seatCost : 'Free'));
    passengerInfo.appendChild(passTable);
  }

  // Baggage
  let baggageTotal = 0;
  const baggageInfo = document.getElementById('baggage-info');
  if (baggageInfo) {
    baggageInfo.textContent = '';

    const includedP = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = 'Included:';
    includedP.appendChild(strong);
    includedP.appendChild(document.createTextNode(' ' + BOOKING.baggage.included));
    baggageInfo.appendChild(includedP);

    const bagTable = document.createElement('table');

    const headerRow = document.createElement('tr');
    const th1 = document.createElement('th');
    th1.textContent = 'Extra Baggage';
    const th2 = document.createElement('th');
    th2.textContent = 'Price';
    headerRow.appendChild(th1);
    headerRow.appendChild(th2);
    bagTable.appendChild(headerRow);

    let hasBaggage = false;
    state.baggage.forEach(bagId => {
      const opt = BOOKING.baggage.options.find(o => o.id === bagId);
      if (opt) {
        hasBaggage = true;
        baggageTotal += opt.price;
        const tr = document.createElement('tr');
        const td1 = document.createElement('td');
        td1.textContent = opt.name;
        const td2 = document.createElement('td');
        td2.textContent = '$' + opt.price;
        tr.appendChild(td1);
        tr.appendChild(td2);
        bagTable.appendChild(tr);
      }
    });

    if (!hasBaggage) {
      const emptyRow = document.createElement('tr');
      const emptyTd = document.createElement('td');
      emptyTd.colSpan = 2;
      emptyTd.textContent = 'Included baggage only';
      emptyRow.appendChild(emptyTd);
      bagTable.appendChild(emptyRow);
    }

    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row';
    const totalTd1 = document.createElement('td');
    totalTd1.textContent = 'Baggage Total';
    const totalTd2 = document.createElement('td');
    totalTd2.textContent = '$' + baggageTotal;
    totalRow.appendChild(totalTd1);
    totalRow.appendChild(totalTd2);
    bagTable.appendChild(totalRow);

    baggageInfo.appendChild(bagTable);
  }

  // Total
  const total = seatCost + baggageTotal;
  document.getElementById('total').textContent = '$' + total;
}

function confirmCheckIn() {
  saveState();
  window.location.href = 'success.html';
}

// Success
function initSuccess() {
  loadState();
  if (!state.validated) {
    window.location.href = 'index.html';
    return;
  }

  renderBoardingPass();
}

function renderBoardingPass() {
  const f = BOOKING.flight;
  const p = BOOKING.passenger;

  const container = document.getElementById('boarding-pass');
  container.textContent = '';

  // Header
  const header = document.createElement('h3');
  header.textContent = 'QUICKFLY - BOARDING PASS';
  container.appendChild(header);

  // Route
  const routeDiv = document.createElement('div');
  routeDiv.className = 'boarding-pass-route';
  routeDiv.textContent = f.departure.airport + ' -----> ' + f.arrival.airport;
  container.appendChild(routeDiv);

  // Grid
  const gridDiv = document.createElement('div');
  gridDiv.className = 'boarding-pass-grid';

  const fields = [
    { label: 'PASSENGER', value: p.lastName + '/' + p.firstName },
    { label: 'FLIGHT', value: f.number },
    { label: 'DATE', value: f.departure.date },
    { label: 'BOARDING', value: f.departure.time },
    { label: 'GATE', value: f.departure.gate },
    { label: 'SEAT', value: state.selectedSeat }
  ];

  fields.forEach(field => {
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'boarding-pass-field';

    const labelDiv = document.createElement('div');
    labelDiv.className = 'label';
    labelDiv.textContent = field.label;
    fieldDiv.appendChild(labelDiv);

    const valueDiv = document.createElement('div');
    valueDiv.className = 'value';
    valueDiv.textContent = field.value;
    fieldDiv.appendChild(valueDiv);

    gridDiv.appendChild(fieldDiv);
  });

  container.appendChild(gridDiv);

  // Notice
  const notice = document.createElement('p');
  notice.style.cssText = 'text-align:center;margin-top:20px;font-size:0.9em;';
  notice.textContent = '*** PLEASE ARRIVE AT GATE 30 MINUTES BEFORE DEPARTURE ***';
  container.appendChild(notice);
}

function downloadPass() {
  const f = BOOKING.flight;
  const p = BOOKING.passenger;
  const seat = state.seat;

  const content = `QUICKFLY - BOARDING PASS
${'='.repeat(40)}
Confirmation: ${BOOKING.confirmation}
Flight: ${f.number}
Route: ${f.departure.airport} → ${f.arrival.airport}
Date: ${f.departure.date}
${'='.repeat(40)}

PASSENGER: ${p.firstName} ${p.lastName}
Seat: ${seat}
Terminal: ${f.departure.terminal}
Gate: ${f.departure.gate}
Departure: ${f.departure.time}

${'='.repeat(40)}
*** ARRIVE AT GATE 30 MINUTES BEFORE DEPARTURE ***
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

function newCheckIn() {
  clearState();
  window.location.href = 'index.html';
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  switch (page) {
    case 'seats': initSeats(); break;
    case 'baggage': initBaggage(); break;
    case 'review': initReview(); break;
    case 'success': initSuccess(); break;
  }
});
