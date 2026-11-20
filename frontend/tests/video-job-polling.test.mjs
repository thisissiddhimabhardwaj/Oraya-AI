import test from 'node:test';
import assert from 'node:assert/strict';
import {hasActiveVideoJobs, pollVideoJobs} from '../src/lib/videoJobPolling.js';

test('idle, terminal and other-lecture jobs do not poll', () => {
  assert.equal(hasActiveVideoJobs([],1),false);
  for (const status of ['completed','failed','render_skipped'])
    assert.equal(hasActiveVideoJobs([{lecture_id:1,status}],1),false);
  assert.equal(hasActiveVideoJobs([{lecture_id:2,status:'rendering'}],1),false);
  for (const status of ['queued','generating_script','generating_visuals','generating_audio','rendering','muxing'])
    assert.equal(hasActiveVideoJobs([{lecture_id:1,status}],1),true);
});

test('active polling waits 2500ms, never overlaps, and stops on cleanup', async () => {
  let callback, pending, calls=0, cleared=false;
  const timers={setTimeout(fn,ms){assert.equal(ms,2500);callback=fn;return 1;},clearTimeout(){cleared=true;}};
  const stop=pollVideoJobs(()=>{calls++;return new Promise(resolve=>{pending=resolve;});},()=>{},timers);
  const tick=callback;callback=null;const response=tick();
  assert.equal(calls,1);assert.equal(callback,null);
  pending();await response;assert.equal(typeof callback,'function');
  stop();assert.equal(cleared,true);
});

test('cleanup while request runs prevents another scheduled request', async () => {
  let callback, resolve, schedules=0;
  const timers={setTimeout(fn){callback=fn;schedules++;return 1;},clearTimeout(){}};
  const stop=pollVideoJobs(()=>new Promise(r=>{resolve=r;}),()=>{},timers);
  const running=callback();stop();resolve();await running;
  assert.equal(schedules,1);
});

test('failed active requests report error and schedule the next bounded poll', async () => {
  let callback, errors=0, schedules=0;
  const timers={setTimeout(fn){callback=fn;schedules++;return 1;},clearTimeout(){}};
  const stop=pollVideoJobs(async()=>{throw Error('unavailable');},()=>errors++,timers);
  await callback();assert.equal(errors,1);assert.equal(schedules,2);stop();
});
