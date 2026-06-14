export default async function handler(req, res) {
  const { token, start_date, end_date } = req.query;
  if (!token) return res.status(400).json({ error: "No token" });

  try {
    const response = await fetch(
      `https://api.ouraring.com/v2/usercollection/sleep?start_date=${start_date}&end_date=${end_date}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    if (!response.ok) return res.status(response.status).json({ error: `Oura API error: ${response.status}` });
    const data = await response.json();
    res.status(200).json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}
