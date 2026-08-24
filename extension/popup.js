const API_BASE = 'https://railspaapi.shohoz.com/v1.0/web';

function renderProfile(profile) {
  const section = document.getElementById('profile-section');
  if (!profile) {
    section.innerHTML = '<div class="status error">Not logged in. Open Railway website and log in first.</div>';
    return;
  }
  section.innerHTML = `
    <div class="profile">
      <div class="label">Name</div>
      <div class="value">${profile.name || profile.full_name || 'N/A'}</div>
      <div class="label">Email</div>
      <div class="value">${profile.email || 'N/A'}</div>
      <div class="label">Mobile</div>
      <div class="value">${profile.mobile || profile.phone || 'N/A'}</div>
    </div>
  `;
}

function loadProfile() {
  chrome.storage.local.get('railway_profile', (result) => {
    if (result.railway_profile) renderProfile(result.railway_profile);
  });

  fetch(`${API_BASE}/auth/profile`, { credentials: 'include', headers: { 'Accept': 'application/json' } })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (data) {
        const profile = data.data || data;
        chrome.storage.local.set({ railway_profile: profile });
        renderProfile(profile);
      }
    })
    .catch(() => {});
}

function getSettings() {
  const preferred = document.getElementById('preferred').value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
  const numSeats = parseInt(document.getElementById('numSeats').value) || 3;
  const startSeat = parseInt(document.getElementById('startSeat').value) || 1;
  const mode = document.getElementById('mode').value;
  const maxS = parseInt(document.getElementById('gauge').value) || 60;
  const clickMode = document.getElementById('clickMode').value;
  const maxRetry = parseInt(document.getElementById('maxRetry').value) || 5;
  const isBurst = clickMode === 'burst';
  const seqFrom = mode === 'priority' ? null : startSeat;

  return { preferred, numSeats, seqFrom, maxS, isBurst, maxRetry };
}

document.getElementById('startBtn').addEventListener('click', async () => {
  const btn = document.getElementById('startBtn');
  const resultDiv = document.getElementById('result');
  const statusDiv = document.getElementById('status');

  btn.disabled = true;
  btn.textContent = 'Running...';
  statusDiv.textContent = '';
  resultDiv.style.display = 'none';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab || !tab.url || !tab.url.includes('eticket.railway.gov.bd')) {
      statusDiv.className = 'status error';
      statusDiv.textContent = 'Open Railway website first!';
      btn.disabled = false;
      btn.textContent = 'START - Auto Select Seats';
      return;
    }

    const s = getSettings();

    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: 'MAIN',
      func: (need, prList, seqFrom, maxS, isBurst, maxRetry) => {
        var attempt = 1;
        var retryDelay = 3;

        function getNum(b) {
          var t = (b.getAttribute('title') || b.textContent || '').trim();
          var m = t.match(/\d+/);
          return m ? parseInt(m[0]) : null;
        }

        function buildMap() {
          var map = new Map();
          document.querySelectorAll('button.btn-seat.seat-available').forEach(function(b) {
            var n = getNum(b);
            if (n && n >= 1 && n <= maxS) map.set(n, b);
          });
          return map;
        }

        function fireClick(b) {
          ['mousedown', 'mouseup', 'click'].forEach(function(t) {
            b.dispatchEvent(new MouseEvent(t, { view: window, bubbles: true, cancelable: true, buttons: 1 }));
          });
        }

        function doAttempt(a) {
          attempt = a;
          var initial = buildMap();
          if (!initial.size) { alert('No available seats! Navigate to seat selection page.'); return; }
          var toClick = [];
          for (var i = 0; i < prList.length && toClick.length < need; i++) {
            if (initial.has(prList[i])) toClick.push(prList[i]);
          }
          if (toClick.length < need) {
            var from = (seqFrom !== null) ? seqFrom : (prList.length ? Math.max.apply(null, prList) + 1 : 1);
            for (var n = from; n <= maxS && toClick.length < need; n++) {
              if (toClick.indexOf(n) < 0 && initial.has(n)) toClick.push(n);
            }
          }
          if (!toClick.length) { alert('Target seats not available!'); return; }
          var gap = isBurst ? 10 : 500;
          var idx = 0;
          function doNext() {
            if (idx >= toClick.length) return;
            var fresh = buildMap();
            var btn = fresh.get(toClick[idx]);
            if (btn) fireClick(btn);
            idx++;
            if (idx < toClick.length) setTimeout(doNext, gap);
          }
          doNext();
          setTimeout(function() {
            var seats = [];
            var seen = new Set();
            ['button.btn-seat.seat-selected', 'button.btn-seat.selected', 'button.btn-seat.active', 'button.btn-seat.booked-by-user'].forEach(function(sel) {
              document.querySelectorAll(sel).forEach(function(b) {
                if (seen.has(b)) return;
                seen.add(b);
                var t = (b.getAttribute('title') || b.textContent || '').trim();
                var m = t.match(/\d+/);
                if (m) seats.push(parseInt(m[0]));
              });
            });
            if (!seats.length) {
              document.querySelectorAll('button.btn-seat').forEach(function(b) {
                var c = b.className || '';
                if (c.indexOf('seat-available') < 0) {
                  var t = (b.getAttribute('title') || b.textContent || '').trim();
                  var m = t.match(/\d+/);
                  if (m) seats.push(parseInt(m[0]));
                }
              });
            }
            var msg = 'Attempt ' + attempt + '/' + maxRetry + '\nClicked: ' + toClick.join(', ') + '\nVerified: ' + seats.length + ' seat(s): ' + seats.join(', ');
            if (seats.length >= need) {
              alert('SUCCESS! ' + seats.length + ' seats:\n' + seats.join(', '));
            } else if (attempt < maxRetry && confirm(msg + '\n\nRetry?')) {
              setTimeout(function() { doAttempt(attempt + 1); }, retryDelay * 1000);
            } else {
              alert(msg);
            }
          }, (toClick.length * gap + 500));
        }

        doAttempt(1);
      },
      args: [s.numSeats, s.preferred, s.seqFrom, s.maxS, s.isBurst, s.maxRetry]
    });

    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="success">Script running on Railway page! Check for alerts.</div>';
    statusDiv.className = 'status success';
    statusDiv.textContent = 'Auto-select executing...';

  } catch (e) {
    statusDiv.className = 'status error';
    statusDiv.textContent = 'Error: ' + e.message;
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="error">' + e.message + '</div>';
  }

  btn.disabled = false;
  btn.textContent = 'START - Auto Select Seats';
});

loadProfile();
