"""Genera mapa_directorio.html a partir de directorio_limpio.json (solo unidades con incluir_mapa = true)."""
import json
from pathlib import Path

D = Path(__file__).parent
unidades = json.load(open(D / "directorio_limpio.json", encoding="utf-8"))["unidades"]
pts = []
for u in unidades:
    if not u["incluir_mapa"] or not u["ubicacion"]: continue
    o = u["oficial"] or {}
    pts.append({"n": u["nombre"], "t": u["tipo"], "d": o.get("direccion") or u["direccion"], "tel": u["telefonos"], "ext": u["extensiones"],
                "h": o.get("horario") or u["horario"], "c": o.get("correo", ""), "u": u["unidad"], "p": u["ubicacion"]["precision"],
                "f": u["ubicacion"]["fuente"], "a": u["alertas"], "lat": round(u["ubicacion"]["lat"], 6), "lon": round(u["ubicacion"]["lon"], 6)})
data = json.dumps(pts, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

HTML = r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Directorio policial - Armando</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css">
<style>html,body,#m{height:100%;margin:0;font:14px system-ui,sans-serif}
.panel{background:#fff;padding:8px 10px;border-radius:6px;box-shadow:0 1px 5px rgba(0,0,0,.4);line-height:1.5;max-width:230px}
.panel b{display:block;margin-bottom:2px}.dot{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:5px;vertical-align:-1px}
.pop small{color:#555}.pop a{color:#0563c1}</style></head><body><div id="m"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const D=__DATA__;
const map=L.map('m').setView([4.6,-74.1],6);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
if(location.protocol==='file:'){const d=document.createElement('div');d.style.cssText='position:absolute;z-index:9999;top:10px;left:60px;right:10px;background:#fff3cd;padding:8px;border:1px solid #c90;font:14px sans-serif';d.textContent='Fondo bloqueado por OSM al abrir como archivo. Abre este mapa con abrir_mapa.bat';document.body.appendChild(d);}
const COL={oficial:'#2e7d32',verificada:'#1565c0',poi:'#ef6c00'};
const NAME={oficial:'Fuente oficial (Sec. Seguridad Bogotá)',verificada:'Verificada manualmente',poi:'OpenStreetMap (sin verificar)'};
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tipos=[...new Set(D.map(p=>p.t))].sort(), activos=new Set(tipos);
const cl=L.markerClusterGroup({chunkedLoading:true});
function pop(p){const tel=p.tel.map(t=>'<a href="tel:'+esc(t.replace(/[^+\d]/g,''))+'">'+esc(t)+'</a>').join(' · ')||'sin teléfono';
 return '<div class="pop"><b>'+esc(p.n)+'</b><br><small>'+esc(p.t)+' · '+esc(p.u)+'</small><br>'+esc(p.d||'(sin dirección)')+'<br>Tel: '+tel+(p.ext.length?' <small>ext. '+esc(p.ext.join(', '))+'</small>':'')
 +(p.h?'<br>'+esc(p.h):'')+(p.c?'<br><a href="mailto:'+esc(p.c)+'">'+esc(p.c)+'</a>':'')+'<br><small>Ubicación: '+esc(NAME[p.p]||p.f)+'</small>'
 +(p.a.length?'<br><small>⚠ '+esc(p.a.join(', '))+'</small>':'')+'</div>';}
const marks=D.map(p=>({p,m:L.circleMarker([p.lat,p.lon],{radius:8,color:'#fff',weight:1.5,fillColor:COL[p.p]||'#777',fillOpacity:.9}).bindPopup(pop(p))}));
function draw(){cl.clearLayers();const v=marks.filter(x=>activos.has(x.p.t));cl.addLayers(v.map(x=>x.m));cnt.textContent=v.length+' de '+D.length+' puntos';}
map.addLayer(cl);
const ctl=L.control({position:'topright'});ctl.onAdd=()=>{const d=L.DomUtil.create('div','panel');L.DomEvent.disableClickPropagation(d);
 d.innerHTML='<b>Directorio policial</b><span id="cnt"></span><hr style="margin:6px 0">'+Object.keys(COL).map(k=>'<div><span class="dot" style="background:'+COL[k]+'"></span>'+NAME[k]+'</div>').join('')
 +'<div id="aviso" style="color:#b26a00;font-size:12px"></div><div><span class="dot" style="background:#1976d2;opacity:.5"></span>Cuadrante con teléfono</div><div><span class="dot" style="background:#c62828;opacity:.5"></span>Cuadrante sin teléfono</div>'
 +'<hr style="margin:6px 0"><b>Tipo</b>'+tipos.map(t=>'<label style="display:block"><input type="checkbox" checked data-t="'+esc(t)+'"> '+esc(t)+' ('+D.filter(p=>p.t===t).length+')</label>').join('');
 d.addEventListener('change',e=>{const t=e.target.dataset.t;e.target.checked?activos.add(t):activos.delete(t);draw();});return d;};ctl.addTo(map);
const cnt=document.getElementById('cnt');draw();
map.createPane('poligonos');map.getPane('poligonos').style.zIndex=350;
const capas=L.control.layers(null,{'Unidades (puntos)':cl},{collapsed:false,position:'bottomright'}).addTo(map);
const rCan=L.canvas({pane:'poligonos',padding:.3});
const aviso=document.getElementById('aviso');const pend={};
function bbox(c,b){if(typeof c[0]==='number'){if(c[0]<b[0])b[0]=c[0];if(c[1]<b[1])b[1]=c[1];if(c[0]>b[2])b[2]=c[0];if(c[1]>b[3])b[3]=c[1];}else c.forEach(x=>bbox(x,b));return b;}
// los poligonos solo se dibujan cerca (zoom) y solo los de la vista actual: dibujar los miles a escala nacional congela el navegador
function cargar(nombre,url,estilo,popup,minZoom,visible){
 let feats=null;const grupo=L.layerGroup();
 function refrescar(){grupo.clearLayers();if(!feats||!map.hasLayer(grupo))return;
  if(map.getZoom()<minZoom){pend[nombre]=1;}else{delete pend[nombre];
   const v=map.getBounds().pad(.1),w=v.getWest(),s=v.getSouth(),e=v.getEast(),n=v.getNorth();
   const sel=feats.filter(x=>x.b[2]>=w&&x.b[0]<=e&&x.b[3]>=s&&x.b[1]<=n);
   if(sel.length>2500){pend[nombre]=1;}else L.geoJSON({type:'FeatureCollection',features:sel.map(x=>x.f)},{renderer:rCan,pane:'poligonos',style:estilo,onEachFeature:(f,ly)=>ly.bindPopup(popup(f.properties))}).addTo(grupo);}
  aviso.textContent=Object.keys(pend).length?'Acerca el zoom para ver: '+Object.keys(pend).join(', '):'';}
 map.on('moveend',refrescar);grupo.on('add',refrescar);grupo.on('remove',()=>{delete pend[nombre];refrescar();});
 fetch(url).then(r=>r.json()).then(g=>{feats=g.features.map(f=>({f,b:bbox(f.geometry.coordinates,[1e9,1e9,-1e9,-1e9])}));
  capas.addOverlay(grupo,nombre+' ('+g.features.length+', zoom ≥ '+minZoom+')');if(visible)grupo.addTo(map);}).catch(e=>console.warn('No se pudo cargar '+url,e));
}
const telLink=t=>t?t.split('|').map(x=>'<a href="tel:'+esc(x)+'">'+esc(x)+'</a>').join(' · '):'sin teléfono';
cargar('Cuadrantes MNVCC','mnvcc_cuadrantes_web.geojson',f=>({color:f.properties.t?'#1976d2':'#c62828',weight:1,fillOpacity:.12}),
 p=>'<div class="pop"><b>'+esc(p.n)+'</b>'+(p.d&&p.d!=='0'?'<br>Municipio (DANE): '+esc(p.d):'')+'<br>Tel: '+telLink(p.t)+'<br><small>Fuente: Policía Nacional, MNVCC</small></div>',11,true);
cargar('Barrios MNVCC','mnvcc_barrios_web.geojson',()=>({color:'#6a1b9a',weight:1,fillOpacity:.05}),
 p=>'<div class="pop"><b>'+esc(p.n)+'</b><br>'+esc(p.m)+', '+esc(p.dp)+'</div>',12,false);
if(D.length){map.fitBounds(L.latLngBounds(D.map(p=>[p.lat,p.lon])),{padding:[30,30]});}

// ---------- Geolocalización ----------
let yo=null,yoCirc=null,primera=true;
function dist(a,b,c,d){const R=6371,r=Math.PI/180,x=(c-a)*r,y=(d-b)*r,h=Math.sin(x/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin(y/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
let cercanaLn=null;
function masCercana(ll){let m=null,dm=1e9;D.forEach(p=>{const k=dist(ll.lat,ll.lng,p.lat,p.lon);if(k<dm){dm=k;m=p;}});
 const c=document.getElementById('cerca');if(!m||!c)return;
 c.innerHTML='<b>Unidad más cercana</b>'+esc(m.n)+'<br><small>'+esc(m.t)+' · a '+(dm<1?Math.round(dm*1000)+' m':dm.toFixed(1)+' km')+' (línea recta)</small><br><a href="#" id="irc">Ver en el mapa</a>';
 document.getElementById('irc').onclick=ev=>{ev.preventDefault();irUnidad(m);};
 if(cercanaLn)cercanaLn.setLatLngs([ll,[m.lat,m.lon]]);else cercanaLn=L.polyline([ll,[m.lat,m.lon]],{color:'#1a73e8',weight:2,dashArray:'6 6',interactive:false}).addTo(map);}
function ubicado(e){
 masCercana(e.latlng);
 if(yo){yo.setLatLng(e.latlng);yoCirc.setLatLng(e.latlng).setRadius(e.accuracy);}
 else{yoCirc=L.circle(e.latlng,{radius:e.accuracy,color:'#1a73e8',weight:1,fillOpacity:.1,interactive:false}).addTo(map);
  yo=L.circleMarker(e.latlng,{radius:8,color:'#fff',weight:2,fillColor:'#1a73e8',fillOpacity:1}).bindTooltip('Estás aquí').addTo(map);}
 if(primera){primera=false;map.setView(e.latlng,Math.max(map.getZoom(),14));}
}
map.on('locationfound',ubicado);
map.on('locationerror',e=>{if(!primera)return;primera=false;msg.textContent='No se pudo obtener tu ubicación ('+e.message+'). Revisa el permiso del navegador.';});
const locBtn=L.control({position:'topleft'});
locBtn.onAdd=()=>{const b=L.DomUtil.create('div','leaflet-bar');const a=L.DomUtil.create('a','',b);a.href='#';a.title='Ir a mi ubicación';a.innerHTML='&#9678;';
 a.style.cssText='font-size:20px;line-height:30px;text-align:center;text-decoration:none;color:#1a73e8';
 L.DomEvent.disableClickPropagation(b);
 L.DomEvent.on(a,'click',ev=>{L.DomEvent.preventDefault(ev);primera=true;map.locate({setView:false,enableHighAccuracy:true,watch:true});});return b;};
locBtn.addTo(map);

// ---------- Buscador ----------
const norm=s=>String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
const idx=D.map(p=>({p,k:norm([p.n,p.d,p.t,p.u].join(' '))}));
const bus=L.control({position:'topleft'});
bus.onAdd=()=>{const d=L.DomUtil.create('div','panel');d.style.width='260px';L.DomEvent.disableClickPropagation(d);L.DomEvent.disableScrollPropagation(d);
 d.innerHTML='<input id="q" type="search" placeholder="Buscar CAI, estación, dirección o lugar…" style="width:100%;box-sizing:border-box;padding:6px">'
  +'<div id="cerca" style="font-size:13px;margin-top:6px"></div><div id="msg" style="font-size:12px;color:#b26a00"></div><div id="res" style="max-height:260px;overflow:auto"></div>';return d;};
bus.addTo(map);
const q=document.getElementById('q'),res=document.getElementById('res'),msg=document.getElementById('msg');
const item=(t,s,fn)=>{const a=document.createElement('div');a.style.cssText='padding:4px 2px;border-top:1px solid #eee;cursor:pointer';
 a.innerHTML='<b style="display:inline">'+esc(t)+'</b><br><small style="color:#555">'+esc(s)+'</small>';a.onclick=fn;a.onmouseenter=()=>a.style.background='#eef';a.onmouseleave=()=>a.style.background='';res.appendChild(a);};
function irUnidad(p){map.flyTo([p.lat,p.lon],17);L.popup().setLatLng([p.lat,p.lon]).setContent(pop(p)).openOn(map);}
function locales(){const t=norm(q.value).split(/\s+/).filter(Boolean);res.innerHTML='';msg.textContent='';if(!t.length)return;
 const r=idx.filter(x=>t.every(w=>x.k.includes(w))).slice(0,8);
 r.forEach(x=>item(x.p.n,x.p.t+' · '+(x.p.d||'sin dirección'),()=>irUnidad(x.p)));
 if(!r.length)msg.textContent='Sin unidades con ese texto. Pulsa Enter para buscar el lugar en el mapa.';
 else{const g=document.createElement('div');g.style.cssText='font-size:12px;color:#555;padding-top:4px';g.textContent='Enter: buscar también como lugar/dirección';res.appendChild(g);}}
async function lugar(){const txt=q.value.trim();if(!txt)return;msg.textContent='Buscando lugar…';
 try{const r=await fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&countrycodes=co&limit=5&q='+encodeURIComponent(txt));const j=await r.json();
  locales();msg.textContent=j.length?'':'Sin resultados de lugar.';
  j.forEach(o=>item(o.display_name.split(',').slice(0,2).join(','),o.display_name,()=>{const bb=o.boundingbox.map(Number);map.flyToBounds([[bb[0],bb[2]],[bb[1],bb[3]]],{maxZoom:17});}));
 }catch(e){msg.textContent='No se pudo consultar el buscador de lugares.';}}
q.addEventListener('input',locales);
q.addEventListener('keydown',e=>{if(e.key==='Enter')lugar();});

// ubicarse automáticamente al abrir (requiere permiso; funciona en localhost/https)
map.locate({setView:false,enableHighAccuracy:true,watch:true});
</script></body></html>"""
(D / "mapa_directorio.html").write_text(HTML.replace("__DATA__", data), encoding="utf-8")
print(f"Mapa generado con {len(pts)} puntos")
