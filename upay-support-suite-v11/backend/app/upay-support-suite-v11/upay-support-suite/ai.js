/* ai.js - support assistant: intent detection, redaction, FAQ matching */
/* ---------- AI assistant logic (from the Message Assistant project) ---------- */
const KB={
failed_txn:{label:"Failed or pending transaction",auto:1,team:"Payments Ops",pri:"high",
 kw:["failed","pending","deducted","not received","taka kete","kete nise","টাকা কেটে","কেটে নিয়েছে","পেন্ডিং","ব্যর্থ"],
 en:e=>`Sorry for the trouble. If money was deducted but the transaction failed, it is normally returned to your wallet automatically within 24 hours. ${e.txn?"We have noted transaction "+e.txn+".":"Please reply with your transaction ID so we can check."} Never share your PIN or OTP with anyone.`,
 bn:e=>`অসুবিধার জন্য দুঃখিত। টাকা কেটে গিয়ে লেনদেন ব্যর্থ হলে সাধারণত ২৪ ঘণ্টার মধ্যে স্বয়ংক্রিয়ভাবে ওয়ালেটে ফেরত আসে। ${e.txn?"আপনার লেনদেন "+e.txn+" আমরা নোট করেছি।":"অনুগ্রহ করে আপনার ট্রানজেকশন আইডি পাঠান।"} কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।`},
wrong_number:{label:"Money sent to wrong number",auto:0,team:"Dispute Desk",pri:"high",
 kw:["wrong number","by mistake","vul number","vul e","ভুল নম্বর","ভুল নাম্বার","ভুলে পাঠ"],
 en:e=>`We are sorry. A completed transfer cannot be reversed automatically, so our dispute team will review your case. Please share the transaction ID and the number you sent to.`,
 bn:e=>`আমরা দুঃখিত। সম্পন্ন হওয়া লেনদেন স্বয়ংক্রিয়ভাবে ফেরত দেওয়া যায় না, তাই আমাদের ডিসপিউট টিম আপনার বিষয়টি দেখবে। অনুগ্রহ করে ট্রানজেকশন আইডি এবং যে নম্বরে পাঠিয়েছেন তা জানান।`},
pin_reset:{label:"Forgot PIN",auto:1,team:"Account Support",pri:"normal",
 kw:["forgot pin","forget pin","reset pin","pin vule","pin bhule","পিন ভুলে","পিন রিসেট","পিন মনে নেই"],
 en:e=>`To reset your PIN, open the upay 2.0 app, tap "Forgot PIN" and follow the steps. upay 2.0 will never ask you for your PIN or OTP.`,
 bn:e=>`পিন রিসেট করতে upay 2.0 অ্যাপ খুলে "পিন ভুলে গেছি" চাপুন এবং ধাপগুলো অনুসরণ করুন। upay 2.0 কখনো আপনার পিন বা ওটিপি চায় না।`},
scam:{label:"Scam or fraud report",auto:0,team:"Fraud Team",pri:"urgent",esc:1,
 kw:["scam","fraud","hacked","asked for otp","otp chaise","fon korse","ওটিপি চেয়ে","প্রতারণা","ফোন করে","lottery","prize","পুরস্কার"],
 en:e=>`Thank you for reporting this. Please do not share your PIN or OTP and do not send any money. We have passed this to our fraud team and they will contact you through the app.`,
 bn:e=>`জানানোর জন্য ধন্যবাদ। অনুগ্রহ করে পিন বা ওটিপি কাউকে দেবেন না এবং কোনো টাকা পাঠাবেন না। বিষয়টি আমাদের ফ্রড টিমকে জানানো হয়েছে, তারা অ্যাপের মাধ্যমে আপনার সাথে যোগাযোগ করবে।`},
fees:{label:"Fees and charges",auto:1,team:"Customer Care",pri:"normal",
 kw:["fee","charge","charges","চার্জ","koto charge","কত কাটবে"],
 en:e=>`Fees depend on the service and the amount. You can see the exact fee on the confirmation screen before you pay, and in the fee list inside the app.`,
 bn:e=>`ফি নির্ভর করে সেবা ও পরিমাণের উপর। পেমেন্টের আগে কনফার্মেশন স্ক্রিনে এবং অ্যাপের ফি তালিকায় সঠিক ফি দেখতে পাবেন।`},
howto:{label:"How to use a service",auto:1,team:"Customer Care",pri:"normal",
 kw:["how to","how do i","kivabe","কীভাবে","কিভাবে"],
 en:e=>`You can do this from the home screen of the app. Tell us which service you need (send money, cash-out, or add money) and we will guide you step by step.`,
 bn:e=>`অ্যাপের হোম স্ক্রিন থেকেই এটি করা যায়। কোন সেবা দরকার (সেন্ড মানি, ক্যাশ আউট, অ্যাড মানি) জানালে ধাপে ধাপে সাহায্য করব।`},
locked:{label:"Account locked or blocked",auto:0,team:"Account Support",pri:"high",
 kw:["locked","blocked","account lock","লক","ব্লক"],
 en:e=>`We are sorry your account is locked. For your safety, a team member will verify your identity and help you. Please do not share your PIN or OTP.`,
 bn:e=>`আপনার অ্যাকাউন্ট লক হওয়ায় আমরা দুঃখিত। নিরাপত্তার জন্য একজন টিম সদস্য আপনার পরিচয় যাচাই করে সাহায্য করবেন। অনুগ্রহ করে পিন বা ওটিপি কাউকে দেবেন না।`},
unknown:{label:"Unclear request",auto:0,team:"Support Agents",pri:"normal",kw:[],
 en:e=>`Thank you for contacting upay 2.0. A support agent will reply to you shortly.`,
 bn:e=>`upay 2.0-এর সাথে যোগাযোগ করার জন্য ধন্যবাদ। একজন সাপোর্ট এজেন্ট শীঘ্রই আপনাকে উত্তর দেবেন।`}};
const BN=/[\u0980-\u09FF]/;
function analyze0(raw){
 const t=raw.toLowerCase(),flags=[],ent={};
 const sens=/(pin|otp|পিন|ওটিপি)\D{0,12}(\d{4,6})/i.test(raw);if(sens)flags.push("Customer typed a PIN or OTP");
 let shown=raw.replace(/(pin|otp|পিন|ওটিপি)(\D{0,12})(\d{4,6})/gi,"$1$2••••").replace(/\b(01\d)(\d{5})(\d{3})\b/g,"$1••••• $3".replace(" ",""));
 if(/\b01\d{9}\b/.test(raw))ent.phone="masked";
 const am=raw.match(/(?:৳|tk\.?|taka|টাকা)\s?([\d,]+)|([\d,]+)\s?(?:৳|tk|taka|টাকা)/i);if(am)ent.amount="৳"+(am[1]||am[2]);
 const tx=raw.match(/\b(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{8,12}\b/);if(tx)ent.txn=tx[0];
 const sc=Object.entries(KB).filter(([k])=>k!=="unknown").map(([k,v])=>[k,v.kw.filter(w=>t.includes(w))]).sort((a,b)=>b[1].length-a[1].length);
 const top=sc[0][1].length?sc[0]:["unknown",[]],intent=top[0],kb=KB[intent],hits=top[1];
 const conf=intent==="unknown"?.3:Math.min(.95,.55+.2*hits.length);
 const bn=BN.test(raw)||hits.some(w=>/^[a-z ]+$/.test(w)&&["taka kete","kete nise","vul number","vul e","pin vule","pin bhule","otp chaise","fon korse","kivabe","koto charge"].includes(w));
 const lang=BN.test(raw)?"Bangla":bn?"Bangla (romanized)":"English";
 let reply=(bn?kb.bn:kb.en)(ent);
 if(sens)reply+=bn?" আপনি বার্তায় গোপন কোড লিখেছেন। অনুগ্রহ করে এটি আর কাউকে দেবেন না।":" You typed a secret code in your message. Please never share it with anyone.";
 let dec=kb.esc?"escalated":(kb.auto&&conf>=.7&&!sens)?"auto_sent":"needs_review";
 return{shown,intent,hits,conf,lang,reply,ent,flags,dec,team:kb.team,pri:kb.pri,policy:kb.label};}
const SW=new Set(["the","is","are","an","to","of","do","i","my","can","what","and","in","for","on","it","me","you","your","please","এবং","কি","কী","আমি","আমার"]);
const tok=t=>new Set((t.toLowerCase().match(/[\u0980-\u09FFa-z0-9]+/g)||[]).filter(w=>w.length>1&&!SW.has(w)));
function faqMatch(raw,FAQS){const A=tok(raw);let best=null;FAQS.forEach(f=>[f.q,...f.alt].forEach(p=>{const B=tok(p);if(!B.size)return;const sh=[...B].filter(w=>A.has(w)),d=2*sh.length/(A.size+B.size),c=B.size>=2?sh.length/B.size*.8:0,sc=Math.max(d,c);if(sc>=.5&&(!best||sc>best.s))best={f,s:sc,sh}}));return best}
function analyze(raw,FAQS=[]){const r=analyze0(raw),m=faqMatch(raw,FAQS);if(!m||r.intent==="scam")return r;
 const sens=r.flags.length>0;let reply=m.f.a;if(sens)reply+=BN.test(m.f.a)?" আপনি বার্তায় গোপন কোড লিখেছেন। অনুগ্রহ করে এটি আর কাউকে দেবেন না।":" You typed a secret code in your message. Please never share it with anyone.";
 return{...r,intent:"faq",policy:"FAQ: "+m.f.q,hits:m.sh,conf:Math.min(.97,.45+m.s*.6),reply,dec:m.f.auto&&!sens?"auto_sent":"needs_review",team:"Customer Care",pri:"normal"}}

const ts=()=>new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
function makeMessage(text,id,faqs){const a=analyze(text,faqs),t=ts();return{id,who:'Customer c_'+(88000+id*37),text,a,at:t,status:a.dec,out:a.dec==='auto_sent'?a.reply:null,draft:a.reply,audit:['Received '+t,'Redacted and analyzed','Matched policy: '+a.policy,'Decision: '+a.dec.replace('_',' ')+(a.dec==='auto_sent'?' and reply sent':'')]}}



/* ---------- On-device smart checks (no network, nothing leaves the phone, every result lists its reasons) ----------
   riskCheck: scores an outgoing Send Money from the customer's OWN history and contacts. Signals: the number is one digit away from
   someone they already pay (typo / look-alike), not found on upay, never paid before, cancelled before, amount far above their
   usual (median based, so one big payment does not hide the next), most of the balance, rapid repeats, late night. It only advises;
   the server still enforces limits, PIN and cancel.
   forecast: recency-weighted daily spend (last 14 days, half-life 5 days, one-off spikes capped), spendable money = free balance minus
   unpaid reminders this month, how long it lasts and what is safe per day until month end, with a confidence note. */
function near1(a,b){/* true when b is a with one digit changed, added, removed, or two neighbours swapped */
  if(!a||!b||a===b)return false;const x=a.length,y=b.length;if(Math.abs(x-y)>1)return false;
  if(x===y){let d=[];for(let i=0;i<x;i++)if(a[i]!==b[i])d.push(i);return d.length===1||(d.length===2&&d[1]===d[0]+1&&a[d[0]]===b[d[1]]&&a[d[1]]===b[d[0]])}
  const [l,s]=x>y?[a,b]:[b,a];for(let i=0;i<l.length;i++)if(l.slice(0,i)+l.slice(i+1)===s)return true;return false}
function riskCheck(hist,phone,amt,now,o){
  o=o||{};const out=(hist||[]).filter(x=>x.a<0&&x.ts&&x.t!=='ক্যাশ আউট'),sends=out.filter(x=>!x.undone),same=out.filter(x=>x.ph===phone),why=[];let s=0,look=null;
  const add=(n,bn,en)=>{s+=n;why.push(L(bn,en))};
  const known=[...(o.known||[]),...sends.filter(x=>x.ph).map(x=>({phone:x.ph,name:x.rn||''}))];
  look=phone&&known.find(k=>k.phone&&k.phone!==phone&&near1(k.phone,phone))||null;
  if(look)add(40,'এই নম্বর আপনার পরিচিত '+(look.name?look.name+' ':'')+look.phone+' নম্বরের সাথে প্রায় একই (একটি অঙ্কের তফাত)। ভুল টাইপ নয় তো?','This number is one digit away from '+(look.name?look.name+' ':'')+look.phone+'. Did you mistype?');
  if(o.exists===false)add(25,'নম্বরটি upay 2.0-তে পাওয়া যায়নি','This number was not found on upay 2.0');
  if(phone&&!same.length){add(20,'এই নম্বরে আগে কখনো পাঠাননি','You have never sent to this number before');if(amt>=5000)add(15,'নতুন নম্বরে বড় অঙ্ক','Large amount to a new number')}
  if(same.some(x=>x.undone))add(30,'এই নম্বরে আগে পাঠিয়ে বাতিল করেছিলেন','You cancelled an earlier send to this number');
  const last=sends.slice(-20).map(x=>Math.abs(x.a)).sort((p,c)=>p-c);
  if(last.length>=3){const med=last[Math.floor(last.length/2)];if(med>0&&amt>=3*med)add(35,'সাধারণত প্রায় '+Math.round(med)+' টাকা পাঠান, এবার '+Math.round(amt/med*10)/10+' গুণ','Your usual send is about '+Math.round(med)+', this is '+Math.round(amt/med*10)/10+'x that')}
  if(o.balance>0&&amt>=0.8*o.balance)add(20,'ব্যালেন্সের প্রায় সবটাই পাঠাচ্ছেন','This is most of your balance');
  if(sends.filter(x=>now-x.ts<6e5).length>=3)add(20,'১০ মিনিটে ৩টির বেশি পাঠিয়েছেন','More than 3 sends in 10 minutes');
  const h=new Date(now).getHours();if(h<5)add(10,'গভীর রাতের লেনদেন','Late-night payment');
  s=Math.min(100,s);const level=s>=60?'high':s>=30?'medium':'low';
  return{score:s,level,reasons:why,lookalike:look,advice:level==='high'?L('প্রাপককে ফোন করে নম্বর মিলিয়ে নিন, বা আগে অল্প টাকা পাঠিয়ে দেখুন।','Confirm the number with the person first, or send a small test amount.'):level==='medium'?L('নম্বরটি আরেকবার দেখে নিন।','Check the number once more.'):''};
}
function forecast(hist,free,now,o){
  o=o||{};const D=864e5,sp=(hist||[]).filter(x=>x.a<0&&x.ts&&!x.undone&&now-x.ts<=14*D);if(sp.length<3||!(free>0))return null;
  const n=Math.max(3,Math.min(14,Math.floor((now-Math.min(...sp.map(x=>x.ts)))/D)+1)),day=Array(n).fill(0);
  sp.forEach(x=>{const k=Math.floor((now-x.ts)/D);if(k<n)day[k]+=Math.abs(x.a)});
  const nz=day.filter(v=>v>0).sort((p,c)=>p-c),med=nz[Math.floor(nz.length/2)]||0,cap=med?3*med:Infinity;
  let sw=0,sd=0;day.forEach((v,k)=>{const w=Math.pow(.5,k/5);sw+=w;sd+=w*Math.min(v,cap)});const avg=sd/sw;if(!(avg>0))return null;
  const reserved=Math.max(0,o.reserved||0),spend=Math.max(0,free-reserved),d=new Date(now),end=new Date(d.getFullYear(),d.getMonth()+1,0).getDate()-d.getDate()+1,left=spend/avg;
  return{avg:Math.round(avg),daysLeft:Math.floor(left),runOut:new Date(now+left*D),safe:Math.floor(spend/end),daysToEnd:end,reserved,
    confidence:n>=7&&sp.length>=6?'good':'low',status:left<end?'short':left<end*1.3?'tight':'ok'};
}
