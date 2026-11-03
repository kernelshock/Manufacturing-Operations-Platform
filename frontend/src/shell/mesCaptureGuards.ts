/** G5.8 capture boundary. The server repeats all authorization and lifecycle checks. */
export function canCaptureOperation(
  operation: { dispatch_id: string } | null,
  selectedDispatchId: string,
  canEdit: boolean,
  dispatchStatus: string | null
): boolean {
  return Boolean(
    operation &&
    operation.dispatch_id === selectedDispatchId &&
    canEdit &&
    dispatchStatus === "RELEASED"
  );
}
