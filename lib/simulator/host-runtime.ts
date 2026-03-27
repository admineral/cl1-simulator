/**
 * Vercel / AWS Lambda-style hosts freeze or discard the isolate after each request,
 * so in-process `setTimeout` tick loops do not reliably run. When true, the simulator
 * advances on GET /api/simulator polling instead.
 */
export function isPollDrivenSimulatorHost(): boolean {
  return (
    process.env.VERCEL === "1" ||
    process.env.AWS_LAMBDA_FUNCTION_NAME !== undefined ||
    process.env.CL_SIM_SERVERLESS === "1"
  );
}
