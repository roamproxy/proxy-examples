// Native fetch (Node 18+) through RoamProxy using undici's ProxyAgent.
//
//   npm install undici
//
// Set ROAM_USER and ROAM_PASS in your environment first.

const { ProxyAgent } = require("undici");

const USER = process.env.ROAM_USER;
const PASS = process.env.ROAM_PASS;
const GATEWAY = "gw.roamproxy.com:41080";

async function getIp(username) {
  const dispatcher = new ProxyAgent(`http://${username}:${PASS}@${GATEWAY}`);
  const res = await fetch("https://ipinfo.io/json", { dispatcher });
  const data = await res.json();
  return data.ip;
}

(async () => {
  console.log("rotating:", await getIp(`${USER}-country-us`));

  const sticky = `${USER}-country-jp-session-demo42`;
  console.log("sticky:  ", await getIp(sticky));
  console.log("sticky:  ", await getIp(sticky));
})();
