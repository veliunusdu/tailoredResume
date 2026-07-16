export function getErrorMessage(
  error: unknown,
  fallback = "An unexpected error occurred."
): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
