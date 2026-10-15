import { errorMessage } from './client'

test('reads field errors from the API error envelope', () => {
  const err = {
    response: { data: { error: { message: 'Invalid input.', details: { load_weight_lb: ['Too big.'] } } } },
  }
  expect(errorMessage(err)).toBe('load weight lb: Too big.')
})

test('falls back to the message, then to network wording', () => {
  expect(errorMessage({ response: { data: { error: { message: 'TomTom error 403' } } } })).toBe(
    'TomTom error 403',
  )
  expect(errorMessage({})).toMatch(/Cannot reach the server/)
})
