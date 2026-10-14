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
  :: c == raise_orbit_small -> fuel = fuel - 10; power = power - 5   /* 5 km  */
  :: c == raise_orbit_big   -> fuel = fuel - 50; power = power - 5   /* 25 km */
  :: c == no_action         -> skip
  fi;
  /* clamp to 0..100 */
  if :: power > 100 -> power = 100 :: else -> skip fi;
  if :: power < 0   -> power = 0   :: else -> skip fi;
  if :: fuel > 100  -> fuel = 100  :: else -> skip fi;
  if :: fuel < 0    -> fuel = 0    :: else -> skip fi;
  /* low power degrades a normal satellite */
  if :: mode == normal && power < 40 -> mode = degraded :: else -> skip fi
}

/* The AI operator: worst case, it may propose ANY command at ANY time. */
active proctype commander() {
  mtype c;
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
       apply(c);
       printf("cmd=%e mode=%e payload=%d power=%d fuel=%d\n", c, mode, payload_on, power, fuel);
       assert(power >= 0 && power <= 100 && fuel >= 0 && fuel <= 100)
     }
  od
}

/* Space weather can change at any moment. */
active proctype environment() {
  do
  :: high_radiation = true
  :: high_radiation = false
  :: severe_storm = true
  :: severe_storm = false
  od
}