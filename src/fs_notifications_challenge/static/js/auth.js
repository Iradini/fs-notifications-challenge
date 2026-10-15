
let currentUser = null;
let fetchPromise = null;

export async function getCurrentUser() {
  if (currentUser) {
    return currentUser;
  }

  // Return in-progress fetch to prevent duplicate API calls
  if (fetchPromise) {
    return fetchPromise;
  }

  const token = localStorage.getItem("access_token");
  if (!token) {
    return null;
  }

  fetchPromise = (async () => {
    try {
      const response = await fetch("/api/auth/me", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        currentUser = await response.json();
        return currentUser;
      }

      localStorage.removeItem("access_token");
      return null;
    } catch (error) {
      console.error("Error fetching current user:", error);
      return null;
    } finally {
      fetchPromise = null;
    }
  })();

  return fetchPromise;
}

export function logout() {
  localStorage.removeItem("access_token");
  currentUser = null;
  window.location.href = "/";
}

export function getToken() {
  return localStorage.getItem("access_token");
}

export function setToken(token) {
  localStorage.setItem("access_token", token);
}

export function clearUserCache() {
  currentUser = null;
}

// fetch() that sends the login token. A 401 means the token is missing, expired
// or no longer valid, so drop it and go to the login page.
export async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(url, { ...options, headers });
  if (response.status == 401) {
    localStorage.removeItem("access_token");
    currentUser = null;
    window.location.href = "/login";
  }
  return response;
}

// Pages that only make sense when logged in: bounce to /login otherwise.
export async function requireUser() {
  const user = await getCurrentUser();
  if (!user) window.location.href = "/login";
  return user; 
}