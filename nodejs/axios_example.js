// Rotating and sticky RoamProxy sessions with axios.
//
//   npm install axios https-proxy-agent
//
// Set ROAM_USER and ROAM_PASS in your environment first.

const axios = require("axios");
const { HttpsProxyAgent } = require("https-proxy-agent");

const USER = process.env.ROAM_USER;
const PASS = process.env.ROAM_PASS;
const GATEWAY = "gw.roamproxy.com:41080";

function agent(username) {
  return new HttpsProxyAgent(`http://${username}:${PASS}@${GATEWAY}`);
}

async function getIp(username) {
  const a = agent(username);
  const { data } = await axios.get("https://ipinfo.io/json", {
    httpAgent: a,
    httpsAgent: a,
    timeout: 30000,
  });
  return data.ip;
}

(async () => {
  // Fresh rotating IP each call.
  console.log("rotating:", await getIp(`${USER}-country-us`));
  console.log("rotating:", await getIp(`${USER}-country-us`));

  // Sticky IP: reuse the session id to keep the same exit.
  const sticky = `${USER}-country-de-session-demo42`;
  console.log("sticky:  ", await getIp(sticky));
  console.log("sticky:  ", await getIp(sticky));
})();
