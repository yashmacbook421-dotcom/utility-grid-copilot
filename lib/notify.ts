import { config } from "./config";

export async function notifySlack(text: string): Promise<[boolean, string | null]> {
  if (!config.slackWebhookUrl) return [false, null];
  try {
    const res = await fetch(config.slackWebhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`Slack returned ${res.status}`);
    return [true, null];
  } catch (e) {
    return [false, e instanceof Error ? e.message : String(e)];
  }
}

export async function notifySms(text: string): Promise<[boolean, string | null]> {
  const sid = process.env.TWILIO_ACCOUNT_SID ?? "";
  const token = process.env.TWILIO_AUTH_TOKEN ?? "";
  const from = process.env.TWILIO_FROM_NUMBER ?? "";
  const to = process.env.TWILIO_TO_NUMBER ?? "";
  if (!sid || !token || !from || !to) return [false, null];

  try {
    const url = `https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: "Basic " + Buffer.from(`${sid}:${token}`).toString("base64"),
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ To: to, From: from, Body: text }).toString(),
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) throw new Error(`Twilio returned ${res.status}`);
    return [true, null];
  } catch (e) {
    return [false, e instanceof Error ? e.message : String(e)];
  }
}
