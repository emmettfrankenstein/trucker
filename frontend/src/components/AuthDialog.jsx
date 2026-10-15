import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'

import { errorMessage } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function AuthDialog({ open, onClose }) {
  const { login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') await login({ username: form.username, password: form.password })
      else await register(form)
      onClose()
    } catch (err) {
      setError(err.response?.status === 401 ? 'Wrong username or password.' : errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth component="form" onSubmit={submit}>
      <Tabs value={mode} onChange={(_, v) => setMode(v)} variant="fullWidth">
        <Tab value="login" label="Sign in" />
        <Tab value="register" label="Create account" />
      </Tabs>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Planning works without an account. Signing in saves your trips to history.
          </Typography>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Username"
            value={form.username}
            onChange={update('username')}
            required
            autoFocus
            autoComplete="username"
          />
          {mode === 'register' && (
            <TextField label="Email (optional)" type="email" value={form.email} onChange={update('email')} />
          )}
          <TextField
            label="Password"
            type="password"
            value={form.password}
            onChange={update('password')}
            required
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            helperText={mode === 'register' ? 'At least 8 characters, not all numbers.' : ' '}
          />
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose}>Cancel</Button>
        <Button type="submit" variant="contained" disabled={busy}>
          {mode === 'login' ? 'Sign in' : 'Create account'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
