chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'FETCH_PROFILE') {
    fetch('https://railspaapi.shohoz.com/v1.0/web/auth/profile', {
      credentials: 'include',
      headers: {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json'
      }
    })
    .then(r => r.json())
    .then(data => {
      const profile = data.data || data;
      chrome.storage.local.set({ railway_profile: profile });
      sendResponse({ profile });
    })
    .catch(e => {
      sendResponse({ profile: null, error: e.toString() });
    });
    return true;
  }
});
