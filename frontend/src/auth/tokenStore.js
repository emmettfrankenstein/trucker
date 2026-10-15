// Tokens live in memory with a localStorage mirror so a reload keeps you signed in.
const KEY = 'trucker.auth'
const listeners = new Set()

function read() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) ?? {}
  } catch {
    return {}
  }
}

let state = read()

export const tokenStore = {
  get access() {
    return state.access
  },
  get refresh() {
    return state.refresh
  },
  set(tokens) {
    state = { ...state, ...tokens }
    try {
      localStorage.setItem(KEY, JSON.stringify(state))
    } catch {
      /* storage unavailable: keep tokens in memory only */
    }
    listeners.forEach((fn) => fn(state))
  },
  clear() {
    state = {}
    try {
      localStorage.removeItem(KEY)
    } catch {
      /* ignore */
    }
    listeners.forEach((fn) => fn(state))
  },
  subscribe(fn) {
    listeners.add(fn)
    return () => listeners.delete(fn)
  },
}
