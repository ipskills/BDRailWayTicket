(function() {
  const API_BASE = 'https://railspaapi.shohoz.com/v1.0/web';

  async function fetchProfile() {
    try {
      const resp = await fetch(`${API_BASE}/auth/profile`, {
        credentials: 'include',
        headers: {
          'Accept': 'application/json, text/plain, */*',
          'Content-Type': 'application/json'
        }
      });
      if (resp.ok) {
        const data = await resp.json();
        return data.data || data;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  async function main() {
    const profile = await fetchProfile();
    if (profile) {
      chrome.storage.local.set({ railway_profile: profile });

      window.parent.postMessage({
        type: 'RAILWAY_PROFILE',
        data: {
          name: profile.name || profile.full_name || '',
          email: profile.email || '',
          mobile: profile.mobile || profile.phone || ''
        }
      }, '*');

      window.postMessage({
        type: 'RAILWAY_PROFILE',
        data: {
          name: profile.name || profile.full_name || '',
          email: profile.email || '',
          mobile: profile.mobile || profile.phone || ''
        }
      }, '*');
    }
  }

  main();

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type === 'GET_PROFILE') {
      chrome.storage.local.get('railway_profile', (result) => {
        sendResponse({ profile: result.railway_profile || null });
      });
      return true;
    }
  });
})();
