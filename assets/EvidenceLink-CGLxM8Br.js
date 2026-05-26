import{h as p,j as e,D as s,m as h}from"./index-DFNhjZjJ.js";/**
 * @license lucide-react v0.507.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const d=[["path",{d:"M7 7h10v10",key:"1tivn9"}],["path",{d:"M7 17 17 7",key:"1vkiza"}]],u=p("arrow-up-right",d);function v({id:n,variant:c="inline",label:a,className:t="",onClick:o}){if(n==null)return null;const i=r=>{r.stopPropagation(),o&&o(r),h(`/evidence/${n}`)},l=a??`Evidence #${n}`;return c==="chip"?e.jsxs("button",{type:"button",onClick:i,title:"Open evidence record","aria-label":`Open evidence record #${n}`,className:`evidence-chip ${t}`.trim(),children:[e.jsx(s,{size:11}),e.jsxs("span",{className:"mono",children:["Evidence #",n]}),e.jsx(u,{size:11,className:"evidence-chip-chevron"})]}):c==="button"?e.jsxs("button",{type:"button",onClick:i,className:`btn sm ${t}`.trim(),children:[e.jsx(s,{size:12}),l]}):e.jsxs("a",{href:`/evidence/${n}`,onClick:i,className:`mono ${t}`.trim(),style:{fontSize:11,color:"var(--ocean-500)",display:"inline-flex",alignItems:"center",gap:4},children:[e.jsx(s,{size:10}),"#",n]})}export{v as E};
