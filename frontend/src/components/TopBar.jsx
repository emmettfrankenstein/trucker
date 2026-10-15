import HistoryIcon from '@mui/icons-material/History'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import LogoutIcon from '@mui/icons-material/Logout'
import { AppBar, Box, Button, Chip, Toolbar, Typography } from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import AuthDialog from './AuthDialog'

export default function TopBar() {
  const { user, logout } = useAuth()
  const [authOpen, setAuthOpen] = useState(false)

  return (
    <AppBar position="static" color="inherit" sx={{ borderBottom: '1px solid #e3e7ee' }} elevation={0}>
      <Toolbar variant="dense" sx={{ gap: 1 }}>
        <Box
          component={RouterLink}
          to="/"
          sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'inherit', textDecoration: 'none' }}
        >
          <LocalShippingIcon color="primary" />
          <Typography variant="h6" component="span">
            Trucker
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ display: { xs: 'none', sm: 'block' } }}>
            Weather-aware truck routing
          </Typography>
        </Box>
        <Box sx={{ flex: 1 }} />
        {user ? (
          <>
            <Button component={RouterLink} to="/history" startIcon={<HistoryIcon />} size="small">
              My trips
            </Button>
            <Chip label={user.username} size="small" sx={{ display: { xs: 'none', sm: 'flex' } }} />
            <Button onClick={logout} startIcon={<LogoutIcon />} size="small" color="inherit">
              Sign out
            </Button>
          </>
        ) : (
          <Button variant="outlined" size="small" onClick={() => setAuthOpen(true)}>
            Sign in
          </Button>
        )}
      </Toolbar>
      <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} />
    </AppBar>
  )
}
