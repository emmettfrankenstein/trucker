import { Alert, AlertTitle } from '@mui/material'

export default function RecommendationBanner({ recommendation }) {
  if (!recommendation?.route) return null
  return (
    <Alert
      severity={recommendation.safe ? 'success' : 'error'}
      variant="outlined"
      sx={{ bgcolor: 'background.paper' }}
    >
      <AlertTitle sx={{ mb: 0.25 }}>
        {recommendation.safe
          ? `Take Route ${recommendation.route}`
          : 'No route is safe at this departure time'}
      </AlertTitle>
      {recommendation.explanation}
    </Alert>
  )
}
