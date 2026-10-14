/* Storm-Safe satellite model (UNGUARDED): the AI can propose any command.
   Rules R1-R5 are checked after each command; SPIN should find a violation.
   Mirrors storm_safe/guard.py -- keep the numbers in sync. */

mtype = { normal, degraded, safe, emergency,           /* modes */
          enter_safe_mode, hibernate_payload, activate_payload,
          reorient_panels, antenna_low, antenna_normal, antenna_high,
          raise_orbit_small, raise_orbit_big, no_action };   /* commands */

mtype mode = normal;
bool payload_on = true;
short power = 80;      /* 0..100 */
short fuel = 60;       /* 0..100 */

/* environment (space weather), free to change at any time */
bool high_radiation = false;
bool severe_storm = false;

inline apply(c) {
  if
  :: c == enter_safe_mode   -> mode = safe; payload_on = false; power = power + 5
  :: c == hibernate_payload -> payload_on = false; power = power + 10
  :: c == activate_payload  -> payload_on = true; power = power - 15
  :: c == reorient_panels   -> power = power - 3
  :: c == antenna_low       -> power = power + 5
  :: c == antenna_normal    -> skip
  :: c == antenna_high      -> power = power - 10
  :: c == raise_orbit_small -> fuel = fuel - 10; power = power - 5
  :: c == raise_orbit_big   -> fuel = fuel - 50; power = power - 5
  :: c == no_action         -> skip
  fi;
  if :: power > 100 -> power = 100 :: else -> skip fi;
  if :: power < 0   -> power = 0   :: else -> skip fi;
  if :: fuel > 100  -> fuel = 100  :: else -> skip fi;
  if :: fuel < 0    -> fuel = 0    :: else -> skip fi;
  if :: (mode == normal && power < 40) -> mode = degraded :: else -> skip fi
}

inline check_rules(c, pre_mode) {
  if :: (c == activate_payload && high_radiation) ->
        printf("VIOLATION R1: payload activated during high radiation\n"); assert(false)
     :: else -> skip fi;
  if :: ((c == raise_orbit_small || c == raise_orbit_big) && pre_mode == safe) ->
        printf("VIOLATION R2: orbit raise in safe mode\n"); assert(false)
     :: else -> skip fi;
  if :: ((c == raise_orbit_small || c == raise_orbit_big) && fuel < 20) ->
        printf("VIOLATION R3: fuel below reserve\n"); assert(false)
     :: else -> skip fi;
  if :: ((c == reorient_panels || c == antenna_low || c == antenna_normal || c == antenna_high) && severe_storm && pre_mode != safe) ->
        printf("VIOLATION R4: storm maneuver outside safe mode\n"); assert(false)
     :: else -> skip fi;
  if :: (power < 15) ->
        printf("VIOLATION R5: power below floor\n"); assert(false)
     :: else -> skip fi
}

active proctype commander() {
  mtype c, pre_mode;
  do
  :: if
     :: c = enter_safe_mode
     :: c = hibernate_payload
     :: c = activate_payload
     :: c = reorient_panels
     :: c = antenna_low
     :: c = antenna_normal
     :: c = antenna_high
     :: c = raise_orbit_small
     :: c = raise_orbit_big
     :: c = no_action
     fi;
     atomic {
       pre_mode = mode;
       apply(c);
       printf("cmd=%e mode=%e payload=%d power=%d fuel=%d\n", c, mode, payload_on, power, fuel);
       check_rules(c, pre_mode)
     }
  od
}

active proctype environment() {
  do
  :: high_radiation = true
  :: high_radiation = false
  :: severe_storm = true
  :: severe_storm = false
  od
}