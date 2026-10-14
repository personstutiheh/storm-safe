/* Storm-Safe satellite model (GUARDED): every command is applied tentatively,
   checked against R1-R5, and rolled back (blocked) if it would break a rule.
   Mirrors storm_safe/guard.py. */

mtype = { normal, degraded, safe, emergency,
          enter_safe_mode, hibernate_payload, activate_payload,
          reorient_panels, antenna_low, antenna_normal, antenna_high,
          raise_orbit_small, raise_orbit_big, no_action };

mtype mode = normal;
bool payload_on = true;
short power = 80;
short fuel = 60;

bool high_radiation = false;
bool severe_storm = false;
bool bad = false;

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

/* Sets `bad` if the command just applied breaks a rule. */
inline violates(c, pre_mode) {
  bad = false;
  if :: (c == activate_payload && high_radiation) -> bad = true :: else -> skip fi;
  if :: ((c == raise_orbit_small || c == raise_orbit_big) && pre_mode == safe) -> bad = true :: else -> skip fi;
  if :: ((c == raise_orbit_small || c == raise_orbit_big) && fuel < 20) -> bad = true :: else -> skip fi;
  if :: ((c == reorient_panels || c == antenna_low || c == antenna_normal || c == antenna_high) && severe_storm && pre_mode != safe) -> bad = true :: else -> skip fi;
  if :: (power < 15) -> bad = true :: else -> skip fi
}

active proctype commander() {
  mtype c, pre_mode, old_mode;
  bool old_payload;
  short old_power, old_fuel;
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
       pre_mode = mode; old_mode = mode; old_payload = payload_on;
       old_power = power; old_fuel = fuel;
       apply(c);
       violates(c, pre_mode);
       if
       :: bad ->   /* GUARD: roll back, command blocked */
            mode = old_mode; payload_on = old_payload;
            power = old_power; fuel = old_fuel;
            printf("BLOCKED  cmd=%e\n", c)
       :: else ->
            printf("accepted cmd=%e mode=%e payload=%d power=%d fuel=%d\n", c, mode, payload_on, power, fuel)
       fi;
       /* SAFETY CLAIM: whatever the state, these must always hold */
       assert(power >= 15 && power <= 100 && fuel >= 0 && fuel <= 100);
       assert(!(c == activate_payload && high_radiation && payload_on && old_payload == false))
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