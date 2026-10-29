"""JavaScript renderer checks run through the public Python test entry point."""
SCRIPT = r'''
// Pure renderer contracts. No browser profile, network or telemetry IO.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),{performance}=require('node:perf_hooks'),path=require('node:path');
const root=process.cwd(),html=fs.readFileSync(path.join(root,'src/evo_compare.html'),'utf8');
function functions(text){return text.slice(text.indexOf('function validate('),text.indexOf('function bounds('));}
function context(text){const c=vm.createContext({});vm.runInContext('let laps=[];'+functions(text)+(text.includes('function speedLimit()')?text.slice(text.indexOf('function speedLimit()'),text.indexOf('function draw()')):''),c);return c;}
function lap(n=3,rows=100){return {simulator_id:'ac_evo',session:{simulator_id:'ac_evo',track:'Circuit',track_layout:'GP'},lap:{number:n,validity:'verified',boundary_interpolation:false,lap_invalidated:false,in_pits:false,sample_count:rows,time_s:1000,track_length_m:5000},data:Array.from({length:rows},(_,i)=>[i*5000/rows,i*.001,-0.,.23456789012345678,.7777777777777778,.3333333333333333,100+i%200*.321+n])};}
const c=context(html);function call(v){c.payload=v;return vm.runInContext('validate(payload)',c);}
if(process.argv.includes('--bench')){
 const oldText=fs.readFileSync(path.join(root,'_local/opt0329/baseline-src/evo_compare.html'),'utf8'),old=context(oldText);
 for(const ctx of [c,old])vm.runInContext(lap.toString()+';payload=Array.from({length:6},(_,i)=>lap(i+1,100000));',ctx);
 vm.runInContext('laps=payload.map(validate)',c);vm.runInContext('laps=payload.map(validate)',old);
 const expected=vm.runInContext('Math.max(1,...laps.map(v=>v.data.reduce((m,r)=>Math.max(m,r[6]),0)))',old);
 const median=a=>a.sort((a,b)=>a-b)[Math.floor(a.length/2)],times={oldValidate:[],newValidate:[],oldSpeed:[],newSpeed:[]};
 function measure(ctx,code,n){const script=new vm.Script(code),start=performance.now();let result;for(let i=0;i<n;i++)result=script.runInContext(ctx);return [(performance.now()-start)/n,result];}
 for(let i=0;i<5;i++){
  for(const name of (i%2?['new','old']:['old','new'])){
   const ctx=name==='new'?c:old;times[name+'Validate'].push(measure(ctx,'payload.forEach(validate)',1)[0]);
   const [ms,value]=measure(ctx,name==='new'?'speedLimit()':'Math.max(1,...laps.map(v=>v.data.reduce((m,r)=>Math.max(m,r[6]),0)))',name==='new'?10000:10);
   assert.equal(value,expected);times[name+'Speed'].push(ms);
  }
 }
 console.log(JSON.stringify({laps:6,samplesPerLap:100000,oldValidationMs:median(times.oldValidate),newValidationMs:median(times.newValidate),oldSpeedLimitMs:median(times.oldSpeed),newSpeedLimitMs:median(times.newSpeed),maximaEqual:true,scope:'validation and speed-scale calculation only; excludes canvas painting'}));
}else{
 const good=lap();good.data.forEach(Object.freeze);Object.freeze(good.data);const before=JSON.stringify(good.data);call(good);
 assert.equal(JSON.stringify(good.data),before);assert(Object.is(good.data[0][2],-0.));assert.equal(good.maximumSpeed,Math.max(...good.data.map(r=>r[6])));
 c.payload=[good];vm.runInContext('laps=payload',c);const expected=vm.runInContext('speedLimit()',c);
 Object.defineProperty(good,'data',{get(){throw Error('Repeated sample scan');}});assert.equal(vm.runInContext('speedLimit()',c),expected);
 for(const bad of [null,Infinity,NaN,true,'1']){const value=lap();value.data[1][4]=bad;assert.throws(()=>call(value));}
 for(const column of [2,3,4,5]){const value=lap();value.data[1][column]=1.011;assert.throws(()=>call(value));}
 for(const column of [0,1,6]){const value=lap();value.data[1][column]=-1;assert.throws(()=>call(value));}
 const nonmono=lap();[nonmono.data[1],nonmono.data[2]]=[nonmono.data[2],nonmono.data[1]];assert.equal(call(nonmono).monotonic,false);
 for(const count of [1,2,3,4,5,6]){c.payload=Array.from({length:count},(_,i)=>call(lap(i+1)));assert.equal(vm.runInContext('validateGroup(payload).length',c),count);}
 for(const count of [0,7]){c.payload=Array.from({length:count},(_,i)=>call(lap(i+1)));assert.throws(()=>vm.runInContext('validateGroup(payload)',c));}
 c.payload=[call(lap()),call(lap()),call(lap())];c.payload[0].session.track_layout='';c.payload[2].session.track_layout='Indy';assert.throws(()=>vm.runInContext('validateGroup(payload)',c));
 c.payload=[call(lap()),call(lap()),call(lap())];c.payload[1].lap.track_length_m=4999.2;c.payload[2].lap.track_length_m=5000.8;assert.throws(()=>vm.runInContext('validateGroup(payload)',c));
 const colorLine=html.split('\n').find(s=>s.startsWith('const colors='));const colors=vm.createContext({StintrixTheme:{mode:'dark'}});vm.runInContext(colorLine,colors);
 for(const mode of ['dark','light']){colors.StintrixTheme.mode=mode;assert.equal(new Set(vm.runInContext('Array.from({length:6},(_,i)=>color(i))',colors)).size,6);}
 console.log('EVO renderer: full values, signed zero, invalid data, six layouts, palette and no repeated speed scan OK');
}
'''

if __name__ == '__main__':
    import shutil, subprocess, sys
    from pathlib import Path
    raise SystemExit(subprocess.run([shutil.which('node') or 'node', '-', *sys.argv[1:]], input=SCRIPT, text=True, encoding='utf-8', cwd=Path(__file__).resolve().parents[1]).returncode)
