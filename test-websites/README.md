# Test Websites for Airline Check-in Agent

> **⚠️ Disclaimer:** These test websites are for **demonstration and educational purposes only**. All airline names, passenger data, flight information, and booking codes are entirely fictitious.

Six static websites with fake data to test the airline check-in agent's capabilities.

## Websites

| Website | Design | Challenge | Passengers | Port |
|---------|--------|-----------|------------|------|
| AnyCompany Airlines | Realistic airline UX | Multi-passenger booking | 3 | 8001 |
| AnyCompany SeatMap | Minimal/functional | Complex seat map | 1 | 8002 |
| AnyCompany SPA | Modern SPA | Dynamic content loading | 2 | 8003 |
| AnyCompany Dialogs | International travel | Conditional fields, passenger types, dialogs | 4 | 8004 |
| AnyCompany Iframes | Budget carrier | iframes, seat conflicts, ambiguous UI | 1 | 8005 |
| AnyCompany Popups | Modern oceanic | Cookie banner, date picker, autocomplete, popups | 1-2 | 8006 |

## Test Credentials

### Website 1: AnyCompany Airlines
- **URL:** http://localhost:8001
- **Confirmation Code:** `SKW789`
- **Last Name:** `Stiles`
- **Passengers:** John Stiles, Mary Major, Mateo Jackson
- **Flight:** AnyCompany 1234, JFK → LAX

### Website 2: AnyCompany SeatMap
- **URL:** http://localhost:8002
- **Confirmation Code:** `QF456`
- **Last Name:** `García`
- **Passenger:** María García
- **Flight:** AnyCompany SeatMap 567, ORD → MIA

### Website 3: AnyCompany SPA
- **URL:** http://localhost:8003
- **Confirmation Code:** `AJ2024`
- **Last Name:** `Santos`
- **Passengers:** Paulo Santos, Saanvi Sarkar
- **Flight:** AnyCompany SPA 890, SEA → DEN

### Website 4: AnyCompany Dialogs
- **URL:** http://localhost:8004
- **Confirmation Code:** `GA7890`
- **Last Name:** `Salazar`
- **Passengers:** Carlos Salazar (adult), Martha Rivera (adult), Sofía Martínez (child), Diego Ramirez (infant)
- **Flight:** AnyCompany Dialogs 456, JFK → LHR (International)

### Website 5: AnyCompany Iframes
- **URL:** http://localhost:8005
- **Confirmation Code:** `BW123`
- **Last Name:** `Roe`
- **Passenger:** Richard Roe
- **Flight:** AnyCompany Iframes 567, ATL → DFW

### Website 6: AnyCompany Popups

- **URL:** http://localhost:8006
- **Confirmation Code:** `PS1234`
- **Last Name:** `Jackson`
- **Departure Date:** `2025-02-15` (must use date picker)
- **Passenger:** Mateo Jackson (can add companion via autocomplete)
- **Flight:** AnyCompany Popups 789, SFO → HNL

## Local Development

### Start all servers:

```bash
cd test-websites && python serve.py
```

### Start individual server:

```bash
python serve.py --site website1-airlines --port 8001
```

## Running the Agent

Pre-configured `.env` files are provided for each test website in the project root.

### Environment Files

| File             | Website            | Credentials        |
| ---------------- | ------------------ | ------------------ |
| `.env.website1`  | AnyCompany Airlines   | Stiles / SKW789    |
| `.env.website2`  | AnyCompany SeatMap    | García / QF456     |
| `.env.website3`  | AnyCompany SPA        | Santos / AJ2024    |
| `.env.website4`  | AnyCompany Dialogs    | Salazar / GA7890   |
| `.env.website5`  | AnyCompany Iframes    | Roe / BW123        |
| `.env.website6`  | AnyCompany Popups     | Jackson / PS1234   |

### Run Commands

```bash
# Website 1: AnyCompany (3 passengers, realistic UX)
uv run --env-file .env.website1 python src/agent.py

# Website 2: AnyCompany SeatMap (complex seat map)
uv run --env-file .env.website2 python src/agent.py

# Website 3: AnyCompany SPA (SPA, dynamic loading)
uv run --env-file .env.website3 python src/agent.py

# Website 4: AnyCompany Dialogs (international, 4 passengers)
uv run --env-file .env.website4 python src/agent.py

# Website 5: AnyCompany Iframes (iframes, seat conflicts)
uv run --env-file .env.website5 python src/agent.py

# Website 6: AnyCompany Popups (cookie banner, date picker, autocomplete)
uv run --env-file .env.website6 python src/agent.py
```

### Headless Mode

To run in headless mode (no browser window), edit the `.env` file and set:

```bash
STRANDS_BROWSER_HEADLESS=true
```

## Deployment to S3/CloudFront

### Prerequisites
- AWS CLI configured with appropriate credentials
- S3 bucket creation permissions
- CloudFront distribution creation permissions

### Deploy all sites:
```bash
./deploy.sh all
```

### Deploy single site:
```bash
./deploy.sh website1-skywest
```

## Key Challenges by Website

### AnyCompany (Realistic)
- 3 passengers requiring individual seat selections
- AnyPlane 700 seat map (3-3 configuration)
- Premium seats with extra cost
- Multi-passenger baggage selection
- Combined boarding pass download

### AnyCompany SeatMap (Minimal)
- Complex AnyPlane 320 seat map with:
  - Emergency exit rows (extra legroom, restrictions)
  - Bulkhead seats
  - 40% random seat unavailability
- Plain HTML forms with minimal styling
- Tests agent's ability to find elements without visual cues

### AnyCompany SPA (SPA)
- Dynamic content loading with delays
- Seat map loads after 2-second spinner
- Seats become unavailable after initial load
- Modal dialogs for confirmations
- Progress bar animations
- QR code boarding pass generation

### AnyCompany Dialogs (International)
- **4 passengers** with different types (2 adults, 1 child, 1 infant)
- **Infant assignment** - must assign infant to an adult passenger
- **Conditional fields:**
  - Passport/expiry required for international flight
  - Visa field appears for non-EU citizens flying to UK
  - State/Province dropdown loads after country selection
- **Dynamic dropdowns** - country list loads with delay, states load based on country
- **Multiple confirmation dialogs** for seat selection (regular + premium seat warning)
- **Terms & Conditions scroll-to-enable** - must scroll to bottom to enable checkbox
- **Final confirmation modal** before completing check-in
- Premium seat rows with surcharges

### AnyCompany Iframes (Budget Carrier)

- **iframe-based seat map** - seat selection happens inside an iframe
- **Seat selection conflicts** - some seats appear available but fail when selected (simulates race condition)
- **Conflict resolution banner** - must dismiss and select new seat
- **Ambiguous button labels:**
  - Login page: "Look Up", "Find", "Continue" all present
  - Seats page: "Random Seat", "Auto Assign", "Continue"
  - Confirm page: "Save for Later", "Confirm", "Complete Check-in"
- **Hidden elements:**
  - Seat options appear only after seat selection
  - Promo section reveals after delay or scroll
  - Skip button appears after 2 seconds
- **Terms & Conditions scroll-to-enable**
- **Countdown timer** on baggage page (5 minutes)
- Cross-frame communication via postMessage

### AnyCompany Popups (AI Agent Challenges)

- **Cookie consent banner** - must dismiss before any page interaction works
  - Blocks page interaction until accepted/rejected
  - Cookie settings modal with granular options
- **Custom date picker calendar** - date field is readonly, must use calendar widget
  - Navigation between months
  - Click day to select date
  - Today highlighting and past date handling
- **Autocomplete/typeahead search** for frequent flyers
  - Debounced input (500ms delay before searching)
  - Loading spinner while "searching"
  - Results dropdown with member details
  - Selection adds passenger to booking
- **Promotional overlay popup** - appears 5 seconds after entering seat selection
  - Modal overlay blocks page
  - Countdown timer (5 minutes)
  - Must close or accept to continue
- **Seat availability alerts** - notifications appear showing seats being taken
  - Appears 15 seconds after page load
  - Auto-dismisses after 8 seconds
- **Terms & Conditions scroll-to-enable** - must scroll to bottom before checkbox works
- **Multiple confirmation modals** throughout the flow
