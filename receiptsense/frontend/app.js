const API_ROOT   = "https://8euvwlthac.execute-api.us-east-1.amazonaws.com/prod";
const UPLOAD_URL = `${API_ROOT}/upload`;
const LIST_URL   = `${API_ROOT}/expenses`;
// ======================================

const $ = id => document.getElementById(id);

// 1. Upload handler
$("send").onclick = async () => {
  const file = $("file").files[0];
  if (!file){ alert("Choose a file"); return; }

  // ask backend for presigned URL
  const res = await fetch(UPLOAD_URL, { method:"POST" });
  const { presigned, key } = await res.json();

  // build a formData per S3 spec
  const fd = new FormData();
  Object.entries(presigned.fields).forEach(([k,v])=>fd.append(k,v));
  fd.append("file", file);

  // upload
  await fetch(presigned.url, { method:"POST", body: fd });
  $("up-msg").textContent = "Uploaded! It may take ~10 s to process.";
};

// 2. Refresh list
$("refresh").onclick = async () => {
  const vendor = $("vendor").value.trim();
  const url = vendor ? `${LIST_URL}?vendor=${encodeURIComponent(vendor)}` : LIST_URL;
  const data = await fetch(url).then(r=>r.json());

  $("tbody").innerHTML = data
  .sort((a, b) => {
    const dateA = a.TxDate || a.Date || "";
    const dateB = b.TxDate || b.Date || "";
    return dateA.localeCompare(dateB);
  })
  .map(r => `<tr><td>${r.TxDate || r.Date}</td><td>${r.Vendor}</td><td>$${r.Total}</td></tr>`)
  .join("");

};

// auto-load on page open
$("refresh").click();
