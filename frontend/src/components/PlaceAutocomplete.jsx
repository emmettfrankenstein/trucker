import PlaceIcon from '@mui/icons-material/Place'
import { Autocomplete, Box, CircularProgress, InputAdornment, TextField, Typography } from '@mui/material'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { geocode } from '../api/endpoints'
import { useDebounce } from '../hooks/useDebounce'

export default function PlaceAutocomplete({ label, value, onChange, error, helperText }) {
  const [input, setInput] = useState('')
  const query = useDebounce(input.trim(), 250)

  const { data: options = [], isFetching } = useQuery({
    queryKey: ['geocode', query.toLowerCase()],
    queryFn: ({ signal }) => geocode(query, signal),
    enabled: query.length >= 3 && query !== value?.label,
    staleTime: 10 * 60_000,
    placeholderData: keepPreviousData,
  })

  return (
    <Autocomplete
      value={value}
      onChange={(_, place) => onChange(place)}
      inputValue={input}
      onInputChange={(_, text) => setInput(text)}
      options={value && !options.some((o) => o.label === value.label) ? [value, ...options] : options}
      getOptionLabel={(o) => o?.label ?? ''}
      isOptionEqualToValue={(a, b) => a.label === b.label && a.lat === b.lat}
      filterOptions={(x) => x}
      noOptionsText={query.length < 3 ? 'Type at least 3 characters' : 'No places found'}
      loading={isFetching}
      autoHighlight
      renderOption={({ key, ...props }, option) => (
        <Box component="li" key={key} {...props} sx={{ gap: 1 }}>
          <PlaceIcon fontSize="small" color="action" />
          <Typography variant="body2">{option.label}</Typography>
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          error={error}
          helperText={helperText}
          size="small"
          slotProps={{
            input: {
              ...params.InputProps,
              startAdornment: (
                <InputAdornment position="start">
                  <PlaceIcon fontSize="small" color={value ? 'primary' : 'disabled'} />
                </InputAdornment>
              ),
              endAdornment: (
                <>
                  {isFetching && <CircularProgress size={16} />}
                  {params.InputProps.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  )
}
