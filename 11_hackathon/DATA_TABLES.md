# Data tables

Every data file in the package: where it is, how much there is, its time span and its columns.
Written by the package builder from the files themselves, so it matches what you received.

Times are UTC unless the column name says local. `<month>` in a file name means one file per calendar month.

## AIS vessel positions (`ais`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/ais/ais_<month>.csv` | 6 | 147.4 MB | 1,313,056 | `BaseDateTime` | 2027-08-15 00:00 | 2028-01-12 05:59 |
| `data/ais/satellite/sais_<month>.csv` | 6 | 6.0 MB | 47,743 | `BaseDateTime` | 2027-08-15 00:05 | 2028-01-12 05:08 |

`ais_<month>.csv` columns: `MMSI`, `BaseDateTime`, `LAT`, `LON`, `SOG`, `COG`, `Heading`, `VesselName`, `IMO`, `CallSign`, `VesselType`, `Status`, `Length`, `Width`, `Draft`, `Cargo`, `TransceiverClass`, `Destination`

`sais_<month>.csv` columns: `MMSI`, `BaseDateTime`, `LAT`, `LON`, `SOG`, `COG`, `Heading`, `VesselName`, `IMO`, `CallSign`, `VesselType`, `Status`, `Length`, `Width`, `Draft`, `Cargo`, `TransceiverClass`, `Destination`

## Port radar and camera contact log (`port_surveillance`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/port_surveillance/camera_events.csv` | 1 | 1.7 MB | 23,628 | `time_utc` | 2027-08-15 00:00 | 2028-01-12 04:00 |
| `data/port_surveillance/radar_tracks_<month>.csv` | 6 | 38.1 MB | 299,426 | `time_utc` | 2027-08-15 00:00 | 2028-01-12 05:59 |
| `data/port_surveillance/sensor_status.csv` | 1 | 2.2 MB | 57,731 | `time_utc` | 2027-08-15 00:00 | 2028-01-12 05:00 |
| `data/port_surveillance/sensors.csv` | 1 | 0.0 MB | 17 | none (static table) |  |  |
| `data/port_surveillance/vessel_traffic_log.csv` | 1 | 0.3 MB | 2,775 | `time_utc` | 2027-08-15 00:04 | 2028-01-11 21:24 |

`camera_events.csv` columns: `time_utc`, `sensor_id`, `event_type`, `direction`, `mmsi`, `vessel_name`, `est_length_m`, `berth_id`, `vessels_in_view`, `water_surface`, `note`

`radar_tracks_<month>.csv` columns: `time_utc`, `sensor_id`, `track_id`, `latitude`, `longitude`, `range_nm`, `bearing_deg`, `speed_kn`, `course_deg`, `est_length_m`, `size_class`, `ais_correlated`, `correlated_mmsi`, `ingest_utc`

`sensor_status.csv` columns: `time_utc`, `sensor_id`, `status`, `detail`

`sensors.csv` columns: `sensor_id`, `sensor_type`, `name`, `latitude`, `longitude`, `range_nm`, `berths_in_view`

`vessel_traffic_log.csv` columns: `time_utc`, `checkpoint`, `direction`, `mmsi`, `vessel_name`, `vessel_class`, `pilot_order_id`, `pilot_boat`, `tugs`, `from_place`, `to_place`

## Coast Guard port conditions and channel status (`port_conditions`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/supply/port_conditions.csv` | 1 | 0.0 MB | 79 | `issued_utc` | 2027-07-30 15:00 | 2027-11-30 15:00 |

`port_conditions.csv` columns: `order_id`, `issued_utc`, `effective_utc`, `authority`, `order_type`, `port_condition`, `segment_id`, `segment_name`, `status`, `vessel_mmsi`, `terminal_id`, `text`

## Vessel arrivals and departures (`port_arrivals`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/supply/vessel_arrivals.csv` | 1 | 0.1 MB | 211 | `noa_submitted_datetime` | 2027-08-04 10:49 | 2028-01-07 09:43 |

`vessel_arrivals.csv` columns: `arrival_id`, `vessel_name`, `mmsi`, `imo_number`, `call_sign`, `flag_state`, `vessel_type`, `port_of_arrival`, `terminal`, `terminal_id`, `berth_id`, `anchorage_position_id`, `draft_arrival_m`, `port_of_departure`, `next_port`, `noa_submitted_datetime`, `eta_datetime`, `eta_revised_datetime`, `ata_anchorage_datetime`, `ata_datetime`, `atd_datetime`, `voyage_number`, `agent`, `noa_status`, `hold_log`, `shift_berth_id`, `shift_datetime`

## Cargo manifests (sea and air relief cargo) (`cargo_manifests`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/supply/cargo_manifest.csv` | 1 | 0.1 MB | 223 | `booking_date` | 2027-07-26 00:00 | 2028-01-03 00:00 |

`cargo_manifest.csv` columns: `manifest_id`, `bl_id`, `bl_type`, `mode`, `direction`, `arrival_id`, `mmsi`, `vessel_name`, `carrier`, `cargo_description`, `hs_commodity_code`, `quantity`, `unit_of_measure`, `cargo_weight_kg`, `shipper_name`, `supplier_id`, `consignee_name`, `consignee_id`, `port_of_lading`, `port_of_discharge`, `booking_date`, `planned_arrival_date`, `arrival_date`, `release_date`, `hazmat_flag`, `un_number`, `container_numbers`

## Fuel deliveries and lots (`fuel_deliveries`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/supply/fuel_deliveries.csv` | 1 | 0.1 MB | 347 | `delivered_utc` | 2027-08-15 13:00 | 2028-01-11 16:06 |

`fuel_deliveries.csv` columns: `record_type`, `ticket_id`, `delivered_utc`, `supplier_id`, `supplier_name`, `facility_id`, `receiving_asset_id`, `product`, `volume_gal`, `lot_id`, `carrier_type`, `carrier_id`, `contract_id`, `tank_level_before_pct`, `tank_level_after_pct`, `received_by`, `remarks`

## ADS-B aircraft positions (`adsb`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/adsb/adsb_<month>.csv` | 6 | 121.8 MB | 976,015 | `time_position` | 2027-08-15 12:25 | 2028-01-12 03:18 |

`adsb_<month>.csv` columns: `icao24`, `callsign`, `origin_country`, `time_position`, `last_contact`, `longitude`, `latitude`, `baro_altitude`, `on_ground`, `velocity`, `true_track`, `vertical_rate`, `sensors`, `geo_altitude`, `squawk`, `spi`, `position_source`, `category`, `nic`, `nac_p`

## Drone detections and authorizations (`drone_detections`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/drone_detections/detections_<month>.csv` | 6 | 14.5 MB | 103,420 | `time_utc` | 2027-08-15 07:51 | 2028-01-12 05:44 |
| `data/drone_detections/laanc_authorizations.csv` | 1 | 0.1 MB | 444 | `issued_utc` | 2027-08-15 10:15 | 2028-01-10 23:01 |
| `data/drone_detections/sensor_sites.csv` | 1 | 0.0 MB | 16 | none (static table) |  |  |
| `data/drone_detections/sensor_status_<month>.csv` | 6 | 2.1 MB | 42,108 | `time_utc` | 2027-08-15 00:00 | 2028-01-12 05:00 |
| `data/drone_detections/sighting_reports.csv` | 1 | 0.0 MB | 68 | `time_utc` | 2027-08-19 14:54 | 2028-01-09 20:56 |

`detections_<month>.csv` columns: `time_utc`, `sensor_id`, `detection_type`, `track_id`, `latitude`, `longitude`, `altitude_m`, `speed_mps`, `course_deg`, `rcs_m2`, `bearing_deg_true`, `range_m`, `rf_center_mhz`, `rf_signature`, `duration_s`, `remote_id`, `authorization_id`, `classification`, `confidence`, `alert`

`laanc_authorizations.csv` columns: `authorization_id`, `authorization_type`, `operator_id`, `airframe_id`, `issued_utc`, `start_utc`, `end_utc`, `center_latitude`, `center_longitude`, `radius_m`, `max_altitude_ft_agl`, `status`

`sensor_sites.csv` columns: `sensor_id`, `name`, `sensor_type`, `owner`, `latitude`, `longitude`, `nominal_range_m`, `reporting_since_utc`, `alert_rcs_threshold_m2`

`sensor_status_<month>.csv` columns: `time_utc`, `sensor_id`, `status`, `detections_last_hour`, `self_test`, `note`

`sighting_reports.csv` columns: `report_id`, `time_utc`, `received_by`, `reporter_type`, `observer_latitude`, `observer_longitude`, `observer_street`, `direction_deg`, `objects_seen`, `duration_min`, `description`, `disposition`

## Authorized drone flight telemetry (`drone_telemetry`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/drone_video/drone_telemetry_<month>.csv` | 6 | 39.4 MB | 175,139 | `timestamp_utc` | 2027-08-15 13:40 | 2028-01-11 21:45 |
| `data/drone_video/drone_telemetry_<month>_argus.csv` | 2 | 40.0 MB | 158,305 | `timestamp_utc` | 2027-09-16 15:05 | 2027-10-29 14:09 |
| `data/drone_video/logs/flight_log.csv` | 1 | 0.1 MB | 445 | `takeoff_utc` | 2027-08-15 13:40 | 2028-01-11 21:41 |
| `data/drone_video/logs/thermal_survey_readings.csv` | 1 | 0.0 MB | 22 | none (static table) |  |  |

`drone_telemetry_<month>.csv` columns: `flight_id`, `frame_number`, `timestamp_utc`, `srt_time`, `latitude`, `longitude`, `rel_alt_m`, `abs_alt_m`, `iso`, `shutter`, `fnum`, `focal_len_mm`, `ev`, `color_temp_k`, `gimbal_pitch_deg`, `gimbal_yaw_deg`, `gimbal_roll_deg`, `course_deg`, `operator_id`, `drone_model`, `mission_name`, `video_filename`

`drone_telemetry_<month>_argus.csv` columns: `flight_id`, `frame_number`, `timestamp_utc`, `srt_time`, `latitude`, `longitude`, `rel_alt_m`, `abs_alt_m`, `iso`, `shutter`, `fnum`, `focal_len_mm`, `ev`, `color_temp_k`, `gimbal_pitch_deg`, `gimbal_yaw_deg`, `gimbal_roll_deg`, `course_deg`, `operator_id`, `drone_model`, `mission_name`, `video_filename`

`flight_log.csv` columns: `flight_id`, `operator_id`, `airframe_id`, `drone_model`, `mission_name`, `authorization_id`, `launch_latitude`, `launch_longitude`, `takeoff_utc`, `landing_utc`, `duration_s`, `track_km`, `max_alt_m_agl`, `sensor`, `spectral_band`, `ground_resolution_m`, `tile_set_id`, `tiles`, `acquisition_start_utc`, `acquisition_end_utc`, `notes`

`thermal_survey_readings.csv` columns: `flight_id`, `tile_set_id`, `asset_id`, `component`, `surface_temp_c`, `ambient_temp_c`, `delta_c`, `sensor`, `spectral_band`, `ground_resolution_m`

## Satellite scene catalogue (`satellite`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/satellite/<scene id>.json` | 171 | 0.3 MB | 171 | `properties.datetime` | 2027-08-15 12:14 | 2028-01-11 16:46 |
| `data/satellite/catalog.json` | 1 | 0.0 MB | 0 | none (static table) |  |  |

`<scene id>.json` columns: `type`, `stac_version`, `stac_extensions`, `id`, `collection`, `geometry`, `bbox`, `links`, `assets`, `properties`

`catalog.json` columns: `type`, `stac_version`, `id`, `description`, `license`, `extent`, `links`

## Structure damage assessments and flood/debris extents (`damage_assessment`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/infrastructure/damage_assessment.csv` | 1 | 5.7 MB | 22,054 | `ASMT_DATE` | 2027-09-14 13:03 | 2028-01-11 16:29 |
| `data/infrastructure/utility_site_survey.csv` | 1 | 0.0 MB | 35 | `survey_time_utc` | 2027-09-17 13:21 | 2027-09-29 13:00 |
| `data/infrastructure/aerial_survey/collection_index.csv` | 1 | 0.0 MB | 6 | `start_utc` | 2027-09-12 14:00 | 2027-09-12 14:00 |

`damage_assessment.csv` columns: `structure_id`, `structure_type`, `address`, `city`, `zip`, `census_tract`, `LATITUDE`, `LONGITUDE`, `DMG_LEVEL`, `ASMT_TYPE`, `ASMT_DATE`, `ASSESSOR`, `OCCUPANCY`, `YEAR_BUILT`, `SQ_FT`, `STORIES`, `FOUNDATION`, `FLOOD_DEPTH_FT`, `ROOF_DAMAGE_PCT`, `ACCESS_NOTE`, `INCIDENT_NUMBER`

`utility_site_survey.csv` columns: `asset_id`, `asset_name`, `LATITUDE`, `LONGITUDE`, `survey_time_utc`, `phase`, `sensor`, `tile_set_id`, `tiles`, `yard_flood_status`, `visible_condition`, `equipment_observation`

`collection_index.csv` columns: `collection_id`, `start_utc`, `end_utc`, `phase`, `sensor`, `tiles`, `coverage`, `targets`

## Response vehicle locations (`avl`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/avl/avl_<YYYY-MM>_<agency>.csv` | 32 | 95.1 MB | 1,274,438 | `time_utc` | 2027-08-15 00:00 | 2028-01-12 07:00 |

`avl_<YYYY-MM>_<agency>.csv` columns: `time_utc`, `unit_id`, `agency`, `latitude`, `longitude`, `speed_kmh`, `heading_deg`, `status`, `incident_number`

## 911 computer-aided dispatch records (`cad_911`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/911/cad_incidents_<month>.csv` | 6 | 26.0 MB | 73,647 | `call_received_dttm` | 2027-08-15 00:01 | 2028-01-11 23:55 |
| `data/911/reports/ali_subscriber_records.csv` | 1 | 4.3 MB | 72,182 | `activation_date` | 2025-12-31 00:00 | 2026-11-22 00:00 |
| `data/911/reports/cbecc_daily_call_volume.csv` | 1 | 0.0 MB | 150 | `date_local` | 2027-08-15 00:00 | 2028-01-11 00:00 |
| `data/911/reports/cbecc_queue_depth.csv` | 1 | 0.0 MB | 309 | `time_utc` | 2027-09-14 00:00 | 2027-09-17 05:00 |
| `data/911/reports/cbecc_shift_log.csv` | 1 | 0.0 MB | 14 | `time_utc` | 2027-09-09 14:00 | 2027-10-30 00:00 |

`cad_incidents_<month>.csv` columns: `incident_number`, `agency`, `call_received_dttm`, `call_answered_dttm`, `dispatch_dttm`, `first_arrival_dttm`, `cleared_dttm`, `priority`, `nature_code`, `nature_description`, `address`, `city`, `state`, `zip`, `beat`, `census_tract`, `latitude`, `longitude`, `unit_id`, `additional_units`, `disposition_code`, `disposition_desc`, `narrative`, `mutual_aid`, `sar_priority`, `sar_case_number`, `transport_destination`, `call_source`, `ali_class_of_service`, `ali_carrier`, `callback_number`, `caller_language`, `call_duration_sec`, `call_taker_position`

`ali_subscriber_records.csv` columns: `callback_number`, `class_of_service`, `carrier`, `service_plan`, `activation_date`, `subscriber_registered`

`cbecc_daily_call_volume.csv` columns: `date_local`, `calls_911`, `calls_ten_digit_lines`, `calls_all_lines`, `incidents_with_unit`, `median_answer_sec`, `p90_answer_sec`, `mutual_aid_dispatcher_hours`, `positions_staffed`

`cbecc_queue_depth.csv` columns: `time_utc`, `pending_calls_and_unassigned_incidents`

`cbecc_shift_log.csv` columns: `time_utc`, `author`, `entry`

## Search and rescue mission log (`sar_missions`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/sar/flood_depth_soundings.csv` | 1 | 0.0 MB | 23 | `time_utc` | 2027-09-16 12:02 | 2027-09-16 13:50 |
| `data/sar/flood_extent_snapshots.csv` | 1 | 0.0 MB | 1 | `time_utc` | 2027-09-16 15:00 | 2027-09-16 15:00 |
| `data/sar/sar_asset_log.csv` | 1 | 0.1 MB | 725 | `time_utc` | 2027-09-11 15:30 | 2027-09-29 00:00 |
| `data/sar/sar_missions.csv` | 1 | 0.3 MB | 1,438 | `delivered_utc` | 2027-09-14 07:24 | 2027-09-24 14:57 |

`flood_depth_soundings.csv` columns: `time_utc`, `agency`, `unit_id`, `latitude`, `longitude`, `address`, `census_tract`, `water_district`, `depth_ft`, `method`

`flood_extent_snapshots.csv` columns: `time_utc`, `area`, `metric`, `value`, `source`

`sar_asset_log.csv` columns: `time_utc`, `asset_id`, `crew_element`, `status`, `location`, `incident_number`, `note`

`sar_missions.csv` columns: `case_number`, `mission_id`, `agency`, `asset_id`, `asset_type`, `crew_element`, `launch_utc`, `on_scene_utc`, `recovery_utc`, `latitude`, `longitude`, `address`, `census_tract`, `persons`, `method`, `outcome`, `delivered_to`, `incident_number`, `delivered_utc`

## Shelter registry and daily census (`shelters`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/shelters/evacuation_bus_trips.csv` | 1 | 0.0 MB | 196 | `pickup_local` | 2027-09-12 07:23 | 2027-09-13 17:04 |
| `data/shelters/shelter_211_calls.csv` | 1 | 0.1 MB | 834 | `call_time_local` | 2027-09-11 06:12 | 2027-09-17 21:55 |
| `data/shelters/shelter_daily_census.csv` | 1 | 0.0 MB | 173 | `date_local` | 2027-09-12 00:00 | 2027-11-15 00:00 |
| `data/shelters/shelter_intake_log.csv` | 1 | 0.1 MB | 1,462 | none (static table) |  |  |
| `data/shelters/shelter_registry.csv` | 1 | 0.0 MB | 6 | `opened_local` | 2027-09-12 08:00 | 2027-09-15 12:00 |

`evacuation_bus_trips.csv` columns: `pickup_local`, `unit_id`, `pickup_area`, `facility_id`, `arrival_local`, `passengers`

`shelter_211_calls.csv` columns: `date_local`, `call_time_local`, `call_id`, `caller_evacuation_zone`, `topic`, `language`, `referred_facility_id`, `note`

`shelter_daily_census.csv` columns: `date_local`, `facility_id`, `facility_name`, `capacity`, `occupancy`, `new_arrivals`, `departures`, `spanish_speaking_pct`, `english_speaking_pct`, `staff_on_duty`, `bilingual_staff_on_duty`, `status`

`shelter_intake_log.csv` columns: `arrival_local`, `facility_id`, `facility_name`, `persons`, `arrival_mode`, `reference`

`shelter_registry.csv` columns: `facility_id`, `facility_name`, `address`, `capacity`, `opened_local`, `closed_local`, `evacuation_zones_served`, `pets`, `medical_station`, `operator`

## Public alerts (EAS, WEA, city and county notices) (`eas_alerts`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/public_health/eas_broadcasts.csv` | 1 | 0.0 MB | 42 | `IssuedAt_UTC` | 2027-08-15 15:10 | 2028-01-11 15:00 |

`eas_broadcasts.csv` columns: `AlertID`, `CAPmsgID`, `EventCode`, `AlertType`, `IssuedAt_UTC`, `ReleasedAt_EN`, `ReleasedAt_ES`, `ExpiresAt_UTC`, `BroadcastChannel`, `WEA_Sent`, `WEA_Sent_EN`, `WEA_Sent_ES`, `GeographicArea`, `AreaIDs`, `Headline_EN`, `Headline_ES`, `AlertSource`, `Priority`, `CharCount_EN`

## Broadcast and translation logs (`broadcast_logs`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/broadcast/alert_relay_log.csv` | 1 | 0.0 MB | 336 | `received_utc` | 2027-08-15 15:10 | 2028-01-11 15:00 |
| `data/broadcast/call_in_log.csv` | 1 | 0.0 MB | 47 | `air_time_utc` | 2027-09-16 16:01 | 2027-09-16 17:59 |
| `data/broadcast/station_program_log.csv` | 1 | 0.2 MB | 1,525 | `air_time_utc` | 2027-09-09 10:00 | 2027-12-13 19:40 |
| `data/broadcast/station_status_log.csv` | 1 | 0.0 MB | 20 | `air_time_utc` | 2027-09-11 12:00 | 2027-10-29 11:00 |
| `data/broadcast/translation_jobs.csv` | 1 | 0.0 MB | 8 | `source_received_utc` | 2027-09-09 14:00 | 2027-10-26 11:00 |

`alert_relay_log.csv` columns: `alert_id`, `station_id`, `station_name`, `received_utc`, `relay_lag_sec`, `result`

`call_in_log.csv` columns: `air_time_utc`, `station_id`, `call_id`, `duration_sec`, `primary_language`, `code_switching`, `english_insertions`, `topic`

`station_program_log.csv` columns: `air_time_utc`, `station_id`, `station_name`, `platform`, `item`, `language`, `alert_id`, `duration_sec`, `description`

`station_status_log.csv` columns: `air_time_utc`, `station_id`, `station_name`, `status`, `note`

`translation_jobs.csv` columns: `job_id`, `alert_id`, `translator`, `source_received_utc`, `translation_delivered_utc`, `first_aired_utc`, `service_level_hours`, `status`, `note`

## Social media posts (`social_media`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/social_media/<account or group>.jsonl` | 316 | 118.6 MB | 114,415 | `created_at` | 2027-07-16 10:19 | 2028-01-12 05:57 |
| `data/social_media/_account_lookup.jsonl` | 1 | 0.6 MB | 2,009 | `lookup_utc` | 2028-01-12 05:00 | 2028-01-12 05:00 |
| `data/social_media/_platform_records_return.jsonl` | 1 | 0.2 MB | 597 | `returned_utc` | 2027-10-14 16:00 | 2027-10-14 16:00 |
| `data/social_media/_geotagged_index.csv` | 1 | 0.1 MB | 1,122 | none (static table) |  |  |

`<account or group>.jsonl` columns: `created_at`, `id`, `id_str`, `full_text`, `truncated`, `entities`, `source`, `in_reply_to_status_id_str`, `in_reply_to_user_id_str`, `in_reply_to_screen_name`, `user`, `coordinates`, `place`, `is_quote_status`, `retweet_count`, `favorite_count`, `lang`

`_account_lookup.jsonl` columns: `id`, `id_str`, `name`, `screen_name`, `location`, `description`, `verified`, `followers_count`, `friends_count`, `statuses_count`, `created_at`, `lookup_utc`, `suspended`

`_platform_records_return.jsonl` columns: `record_type`, `referral`, `returned_utc`, `screen_name`, `user_id_str`, `event_utc`, `event`, `source_ip`, `asn`, `asn_name`, `asn_country`, `client`

`_geotagged_index.csv` columns: `id_str`, `screen_name`, `created_utc`, `latitude`, `longitude`

## Official statements and notices (`public_record`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/press_releases/statements_<month>.jsonl` | 7 | 0.2 MB | 180 | `issued_local` | 2027-07-16 05:52 | 2028-01-11 05:23 |

`statements_<month>.jsonl` columns: `id`, `issued_local`, `date_local`, `time_local`, `issuer`, `type`, `text`, `speakers`, `places`

## Surface weather and buoy observations (`weather`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/weather/<station>_observations.csv` | 2 | 0.9 MB | 7,212 | `ObsDateTime` | 2027-08-15 00:50 | 2028-01-12 05:50 |
| `data/weather/<station>_ASOS_observations.csv` | 7 | 3.8 MB | 25,056 | `ObsDateTime` | 2027-08-15 00:53 | 2028-01-12 05:53 |

`<station>_observations.csv` columns: `StationID`, `StationName`, `StnLat`, `StnLon`, `ObsDateTime`, `WDIR_degT`, `WSPD_mps`, `GST_mps`, `WVHT_m`, `DPD_s`, `APD_s`, `MWD_degT`, `PRES_mb`, `ATMP_C`, `WTMP_C`, `DEWP_C`

`<station>_ASOS_observations.csv` columns: `USAF`, `WBAN`, `StationID`, `StationName`, `StnLat`, `StnLon`, `StnElev_m`, `ObsDateTime`, `ReportType`, `SkyCondition`, `CloudBaseAGL_ft`, `Visibility_m`, `PresentWx`, `DryBulbTemp_C`, `DewPoint_C`, `RelativeHumidity_pct`, `WindDir_deg`, `WindSpeed_mps`, `WindGust_mps`, `StationPressure_mb`, `SeaLevelPressure_mb`, `Precip1hr_mm`, `Remarks`

## Hurricane advisories and best track (`storm_advisories`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/weather/nhc_advisories.json` | 1 | 0.1 MB | 68 | `advisories[].issued_utc` | 2027-09-02 15:00 | 2027-09-15 15:00 |

`nhc_advisories.json` columns: `storm`, `atcf_id`, `basin`, `season`, `source_format`, `times`, `count`, `advisories`, `best_track`

## Tide and river gauges (`tide_river_gauges`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/env_sensors/gauge_<id>.csv` | 8 | 34.3 MB | 238,179 | `ObsDateTime` | 2027-08-15 00:00 | 2028-01-12 05:54 |

`gauge_<id>.csv` columns: `SensorID`, `SensorName`, `Latitude`, `Longitude`, `ObsDateTime`, `Stage_ft`, `Discharge_cfs`, `WaterTemp_C`, `SpecificConductance_uScm`, `Quality`

## Water-quality sondes (`water_quality`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/env_sensors/water_quality_<id>.csv` | 6 | 10.9 MB | 85,743 | `ObsDateTime` | 2027-08-15 00:00 | 2028-01-12 05:45 |

`water_quality_<id>.csv` columns: `SensorID`, `SensorName`, `Latitude`, `Longitude`, `ObsDateTime`, `WaterTemp_C`, `SpecificConductance_uScm`, `Salinity_psu`, `DissolvedOxygen_mgL`, `pH`, `Turbidity_NTU`, `TotalHydrocarbons_ppb`, `Depth_m`, `Battery_V`, `QC`

## Air-quality monitors (`air_quality`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/env_sensors/aqs_air_quality_<id>.csv` | 20 | 8.3 MB | 69,888 | `Date_GMT` | 2027-08-15 00:00 | 2028-01-12 00:00 |

`aqs_air_quality_<id>.csv` columns: `SensorID`, `State_Code`, `County_Code`, `Site_Name`, `Site_Type`, `Latitude`, `Longitude`, `Date_GMT`, `Time_GMT`, `PM25_ugm3`, `Ozone_ppb`, `SO2_ppb`, `H2S_ppb`, `Benzene_ppb`, `TNMHC_ppbC`, `WindSpeed_mps`, `WindDir_deg`, `Temp_C`, `QC`

## Wastewater pathogen surveillance (`wastewater`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/public_health/wastewater_surveillance.csv` | 1 | 0.1 MB | 488 | `report_date` | 2027-08-14 00:00 | 2028-01-12 00:00 |

`wastewater_surveillance.csv` columns: `sample_id`, `sample_date`, `sewershed_id`, `site_name`, `sample_type`, `target`, `concentration_gc_per_L`, `pmmov_gc_per_L`, `normalized_ratio`, `flow_MGD`, `lab_qc`, `report_date`

## Emergency department visits (`ed_visits`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/public_health/ed_visits_<id>.csv` | 7 | 18.7 MB | 90,895 | `Arrive_Date_Time` | 2027-08-15 05:10 | 2028-01-12 05:59 |

`ed_visits_<id>.csv` columns: `Visit_ID`, `Facility_ID`, `Facility_Name`, `Patient_Class`, `Visit_Date`, `Arrive_Date_Time`, `Arrival_Mode`, `Triage_Acuity_ESI`, `Chief_Complaint_Text`, `CC_Category`, `Age`, `Age_Group`, `Sex`, `Race_Ethnicity`, `Preferred_Language`, `Patient_ZIP`, `Patient_Tract`, `Onset_Date`, `Disposition`, `Discharge_Diagnosis_ICD10`, `Facility_County`

## Hospital capacity and utilities status (`hospital_capacity`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/public_health/hospital_capacity.csv` | 1 | 0.2 MB | 1,050 | `Report_Date` | 2027-08-15 00:00 | 2028-01-11 00:00 |

`hospital_capacity.csv` columns: `Report_Date`, `Facility_ID`, `Facility_Name`, `Census_Time_Local`, `Licensed_Beds`, `Staffed_Beds_Available`, `Inpatient_Census`, `Pct_Licensed_Occupancy`, `Census_Target`, `ICU_Beds`, `ICU_Occupied`, `ED_Beds`, `ED_Visits_24h`, `ED_Boarding`, `Hallway_Patients`, `Triage_Tent_Patients`, `Elective_Procedures_Postponed`, `Ventilators_Total`, `Ventilators_In_Use`, `Diversion_Status`, `Staffing_Level`, `Mutual_Aid`, `Power_Source`, `Commercial_Power_Lost_UTC`, `Generator_Start_UTC`, `Commercial_Power_Restored_UTC`, `Generator_Hours_Cumulative`, `Generator_Test`, `Diesel_Tank_A_gal`, `Diesel_Tank_B_gal`, `Diesel_On_Hand_gal`, `Burn_Rate_gph`, `Fuel_Hours_Remaining`, `Est_Runtime_Days_At_Storm_Load`, `Fuel_Delivered_gal`

## Syndromic surveillance summary (`syndromic`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/public_health/syndrome_summary.csv` | 1 | 2.8 MB | 57,701 | `Report_Date` | 2027-08-15 00:00 | 2028-01-11 00:00 |

`syndrome_summary.csv` columns: `Report_Date`, `Facility_ID`, `Area_ID`, `CC_Category`, `Visit_Count`, `Admitted_Count`

## Utility SCADA historian (`scada_historian`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/telemetry/historian_BOOSTERS_<month>.csv` | 6 | 6.2 MB | 117,411 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 00:30 |
| `data/telemetry/historian_DIST_<month>.csv` | 6 | 5.4 MB | 99,532 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 05:40 |
| `data/telemetry/historian_DSS01_<month>.csv` | 6 | 2.3 MB | 44,064 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 05:45 |
| `data/telemetry/historian_GEN01_<month>.csv` | 6 | 1.0 MB | 18,956 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 05:15 |
| `data/telemetry/historian_SUB01_<month>.csv` | 6 | 5.0 MB | 98,174 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 04:15 |
| `data/telemetry/historian_SUB02_<month>.csv` | 6 | 4.6 MB | 91,557 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 04:50 |
| `data/telemetry/historian_SUB03_<month>.csv` | 6 | 4.3 MB | 85,118 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 02:15 |
| `data/telemetry/historian_SUB04_<month>.csv` | 6 | 4.6 MB | 90,347 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 02:10 |
| `data/telemetry/historian_SUB05_<month>.csv` | 6 | 4.5 MB | 88,792 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 03:25 |
| `data/telemetry/historian_SYSTEM_<month>.csv` | 6 | 3.0 MB | 58,115 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 06:00 |
| `data/telemetry/historian_TANKS_<month>.csv` | 6 | 8.2 MB | 168,478 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 05:05 |
| `data/telemetry/historian_WTP_<month>.csv` | 6 | 10.6 MB | 200,257 | `Timestamp` | 2027-08-15 00:00 | 2028-01-12 06:00 |

`historian_BOOSTERS_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_DIST_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_DSS01_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_GEN01_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_SUB01_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_SUB02_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_SUB03_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_SUB04_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_SUB05_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_SYSTEM_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_TANKS_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

`historian_WTP_<month>.csv` columns: `Tagname`, `Timestamp`, `Value`, `Quality`

## Customer outages by area (`outage_map`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/telemetry/outage_map.csv` | 1 | 7.0 MB | 76,728 | `timestamp_utc` | 2027-09-10 05:00 | 2027-10-27 05:00 |

`outage_map.csv` columns: `timestamp_utc`, `area_id`, `feeder_id`, `substation_id`, `customers_served`, `customers_out`, `cause`, `crews_assigned`, `est_restoration_utc`

## Maintenance work orders and purchase requests (`work_orders`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/maintenance/work_orders.csv` | 1 | 0.3 MB | 754 | `reported_date` | 2027-07-21 14:12 | 2028-01-11 21:06 |

`work_orders.csv` columns: `wonum`, `org_id`, `site_id`, `description`, `work_type`, `status`, `status_date`, `reported_date`, `asset_id`, `location`, `priority`, `sched_start`, `sched_finish`, `actual_start`, `actual_finish`, `labor_hours`, `reported_by`, `lead`, `crew`, `failure_code`, `vendor_id`, `pr_number`, `parent_wonum`, `status_history`, `work_log`

## Military installation status reports (`base_status_reports`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/maintenance/base_status_reports.csv` | 1 | 0.1 MB | 600 | `reported_utc` | 2027-08-15 21:54 | 2028-01-11 23:41 |

`base_status_reports.csv` columns: `report_date`, `reported_utc`, `installation_id`, `installation_name`, `readiness_pct`, `aircraft_on_station`, `flight_ops_status`, `backup_power_status`, `equipment_id`, `generator_last_test_date`, `generator_test_result`, `perimeter_sensor_status`, `production_status`, `facility_status`, `remarks`

## Utility security alerts (`siem_alerts`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/network_logs/siem/daily_summary.csv` | 1 | 0.0 MB | 181 | `date_utc` | 2027-07-16 00:00 | 2028-01-12 00:00 |
| `data/network_logs/siem/rule_changes.csv` | 1 | 0.0 MB | 7 | `time_utc` | 2027-08-19 11:34 | 2027-10-19 00:30 |
| `data/network_logs/siem/siem_alerts_<month>.csv` | 7 | 91.6 MB | 459,464 | `time_utc` | 2027-07-16 00:00 | 2028-01-12 23:59 |

`daily_summary.csv` columns: `date_utc`, `alerts`, `closed_false_positive`, `false_positive_rate_pct`, `open_ml_anomaly_alerts`

`rule_changes.csv` columns: `time_utc`, `action`, `rule_id`, `rule_type`, `description`, `changed_by`, `change_ticket`

`siem_alerts_<month>.csv` columns: `alert_id`, `time_utc`, `rule_id`, `rule_name`, `category`, `priority`, `src_host`, `src_ip`, `dst_host`, `dst_ip`, `dst_port`, `user`, `detail`, `disposition`, `closed_utc`, `closed_by`, `close_note`

## Network connection logs (`zeek_logs`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/network_logs/zeek/<YYYY-MM-DD>/conn.log` | 181 | 45.9 MB | 352,082 | `ts` | 2027-07-16 00:00 | 2028-01-12 23:59 |
| `data/network_logs/zeek/<YYYY-MM-DD>/dns.log` | 181 | 17.1 MB | 107,777 | `ts` | 2027-07-16 00:00 | 2028-01-12 23:59 |
| `data/network_logs/zeek/<YYYY-MM-DD>/notice.log` | 181 | 0.1 MB | 559 | `ts` | 2027-07-16 00:00 | 2028-01-12 23:59 |
| `data/network_logs/zeek/<YYYY-MM-DD>/ssl.log` | 181 | 7.1 MB | 52,570 | `ts` | 2027-07-16 00:00 | 2028-01-12 23:59 |

`conn.log` columns: `ts`, `uid`, `id.orig_h`, `id.orig_p`, `id.resp_h`, `id.resp_p`, `proto`, `service`, `duration`, `orig_bytes`, `resp_bytes`, `conn_state`, `local_orig`, `local_resp`, `missed_bytes`, `history`, `orig_pkts`, `orig_ip_bytes`, `resp_pkts`, `resp_ip_bytes`

`dns.log` columns: `ts`, `uid`, `id.orig_h`, `id.orig_p`, `id.resp_h`, `id.resp_p`, `proto`, `trans_id`, `query`, `qclass_name`, `qtype_name`, `rcode_name`, `AA`, `RD`, `RA`, `answers`, `TTLs`

`notice.log` columns: `ts`, `uid`, `id.orig_h`, `id.resp_h`, `id.resp_p`, `note`, `msg`, `src`, `dst`, `p`, `actions`

`ssl.log` columns: `ts`, `uid`, `id.orig_h`, `id.orig_p`, `id.resp_h`, `id.resp_p`, `version`, `cipher`, `server_name`, `resumed`, `established`

## Host, access and mail audit logs (`host_audit_logs`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/network_logs/audit/account_logons_city_airstation.csv` | 1 | 0.3 MB | 2,610 | `time_utc` | 2027-09-12 00:02 | 2027-09-21 23:56 |
| `data/network_logs/audit/alarm_suppression_audit.csv` | 1 | 0.0 MB | 176 | `time_utc` | 2027-07-02 21:28 | 2027-10-12 15:26 |
| `data/network_logs/audit/change_management.csv` | 1 | 0.0 MB | 145 | `time_utc` | 2027-07-17 13:10 | 2028-01-08 15:59 |
| `data/network_logs/audit/endpoint_protection.csv` | 1 | 0.6 MB | 7,342 | `time_utc` | 2027-07-15 00:53 | 2028-01-12 23:44 |
| `data/network_logs/audit/file_integrity.csv` | 1 | 0.0 MB | 161 | `time_utc` | 2027-07-24 15:39 | 2028-01-09 17:02 |
| `data/network_logs/audit/historian_access.csv` | 1 | 0.2 MB | 1,326 | `start_utc` | 2027-07-16 13:05 | 2028-01-13 00:27 |
| `data/network_logs/audit/mail_gateway_airstation.csv` | 1 | 0.3 MB | 1,260 | `time_utc` | 2027-09-12 00:01 | 2027-09-21 23:44 |
| `data/network_logs/audit/mail_gateway_brightwake.csv` | 1 | 0.2 MB | 1,001 | `time_utc` | 2027-07-16 00:14 | 2027-08-24 22:42 |
| `data/network_logs/audit/mail_gateway_cbpwa.csv` | 1 | 3.7 MB | 20,943 | `time_utc` | 2027-07-15 00:11 | 2028-01-12 23:52 |
| `data/network_logs/audit/mail_gateway_city.csv` | 1 | 0.5 MB | 2,440 | `time_utc` | 2027-09-12 00:21 | 2027-09-21 23:57 |
| `data/network_logs/audit/mail_url_clicks_brightwake.csv` | 1 | 0.0 MB | 1 | `time_utc` | 2027-08-12 15:02 | 2027-08-12 15:02 |
| `data/network_logs/audit/mail_url_clicks_city_airstation.csv` | 1 | 0.0 MB | 10 | `time_utc` | 2027-09-15 14:15 | 2027-09-17 11:30 |
| `data/network_logs/audit/ot_config_changes.csv` | 1 | 0.0 MB | 93 | `time_utc` | 2027-07-20 17:23 | 2028-01-07 21:52 |
| `data/network_logs/audit/remote_access_sessions.csv` | 1 | 0.1 MB | 843 | `login_utc` | 2027-07-16 12:56 | 2028-01-12 22:53 |
| `data/network_logs/audit/scada_command_log.csv` | 1 | 0.0 MB | 401 | `time_utc` | 2027-07-16 02:47 | 2028-01-12 19:45 |
| `data/network_logs/audit/settings_audits.csv` | 1 | 0.0 MB | 5 | `time_utc` | 2027-09-28 22:02 | 2027-10-02 21:40 |

`account_logons_city_airstation.csv` columns: `time_utc`, `service`, `account`, `src_ip`, `src_network`, `result`, `auth_method`, `device`

`alarm_suppression_audit.csv` columns: `time_utc`, `system`, `action`, `alarm_point`, `category`, `changed_by`, `source_host`, `change_ticket`, `active_suppressions_after`

`change_management.csv` columns: `time_utc`, `record_id`, `record_type`, `summary`, `owner`, `status`

`endpoint_protection.csv` columns: `time_utc`, `host`, `ip`, `event`, `detail`, `initiated_by`

`file_integrity.csv` columns: `time_utc`, `host`, `path`, `event`, `previous_hash`, `new_hash`, `user`, `source_host`, `diff_summary`

`historian_access.csv` columns: `session_id`, `server`, `account`, `client_host`, `start_utc`, `end_utc`, `duration_s`, `tags_queried`, `tag_groups`, `query_type`

`mail_gateway_airstation.csv` columns: `time_utc`, `gateway`, `direction`, `sender`, `sender_domain`, `recipient`, `subject`, `attachment_names`, `size_bytes`, `verdict`, `action`, `message_id`

`mail_gateway_brightwake.csv` columns: `time_utc`, `gateway`, `direction`, `sender`, `sender_domain`, `recipient`, `subject`, `attachment_names`, `size_bytes`, `verdict`, `action`, `message_id`

`mail_gateway_cbpwa.csv` columns: `time_utc`, `gateway`, `direction`, `sender`, `sender_domain`, `recipient`, `subject`, `attachment_names`, `size_bytes`, `verdict`, `action`, `message_id`

`mail_gateway_city.csv` columns: `time_utc`, `gateway`, `direction`, `sender`, `sender_domain`, `recipient`, `subject`, `attachment_names`, `size_bytes`, `verdict`, `action`, `message_id`

`mail_url_clicks_brightwake.csv` columns: `time_utc`, `gateway`, `mailbox`, `message_id`, `url_host`, `client_ip`, `sender_network`

`mail_url_clicks_city_airstation.csv` columns: `time_utc`, `gateway`, `mailbox`, `url_host`, `client_ip`

`ot_config_changes.csv` columns: `time_utc`, `device`, `parameter`, `old_value`, `new_value`, `change_type`, `session_user`, `source_host`, `change_ticket`

`remote_access_sessions.csv` columns: `session_id`, `gateway`, `account`, `src_ip`, `src_network`, `src_country`, `login_utc`, `logout_utc`, `duration_s`, `bytes_out`, `bytes_in`, `auth_method`, `target_hosts`, `change_ticket`

`scada_command_log.csv` columns: `time_utc`, `scada_server`, `workstation`, `operator`, `command`, `device`, `result`, `origin`, `console_session_id`, `origin_host`

`settings_audits.csv` columns: `time_utc`, `audit`, `device`, `site`, `item`, `found`, `record_value`, `record_date`, `result`

## Aid portal and logistics system access logs (`portal_access_logs`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/network_logs/portal/aid_portal_access_<month>.csv` | 7 | 50.5 MB | 396,213 | `time_utc` | 2027-07-16 00:27 | 2028-01-12 23:05 |
| `data/network_logs/portal/base_logistics_access_<month>.csv` | 7 | 1.1 MB | 8,724 | `time_utc` | 2027-07-16 00:04 | 2028-01-12 23:52 |

`aid_portal_access_<month>.csv` columns: `time_utc`, `system`, `client_ip`, `client_network`, `method`, `path`, `status`, `event`, `account_ref`, `user_agent_family`, `bytes`

`base_logistics_access_<month>.csv` columns: `time_utc`, `system`, `client_ip`, `client_network`, `method`, `path`, `status`, `event`, `account_ref`, `user_agent_family`, `bytes`

## Tanker cargo-control and vendor remote-access logs (`vessel_ot_logs`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/telemetry/vessel_cargo_control_kalvora_star.csv` | 1 | 1.9 MB | 19,823 | `timestamp_utc` | 2027-07-16 05:00 | 2028-01-12 00:30 |
| `data/telemetry/vessel_cargo_control_ostrel_bay.csv` | 1 | 1.9 MB | 20,533 | `timestamp_utc` | 2027-07-16 05:00 | 2028-01-12 00:30 |
| `data/telemetry/vessel_cargo_control_remote_sessions.csv` | 1 | 0.0 MB | 74 | `login_utc` | 2027-07-19 09:18 | 2027-11-18 15:10 |

`vessel_cargo_control_kalvora_star.csv` columns: `timestamp_utc`, `mmsi`, `vessel_name`, `record_type`, `station`, `operator`, `tag`, `value`, `unit`, `text`

`vessel_cargo_control_ostrel_bay.csv` columns: `timestamp_utc`, `mmsi`, `vessel_name`, `record_type`, `station`, `operator`, `tag`, `value`, `unit`, `text`

`vessel_cargo_control_remote_sessions.csv` columns: `session_id`, `gateway`, `vendor_account`, `src_ip`, `src_asn`, `target_system`, `vessel_mmsi`, `vessel_name`, `login_utc`, `logout_utc`, `duration_s`, `access_level`, `ticket_ref`, `result`, `bytes_out`

## Vendor registry, contracts and invoices (`contracts`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/payments/contracts_actions.csv` | 1 | 0.0 MB | 72 | `action_date` | 2027-08-28 00:00 | 2027-12-27 00:00 |
| `data/payments/contracts_awards.csv` | 1 | 0.0 MB | 32 | `award_date` | 2027-08-28 00:00 | 2027-11-19 00:00 |
| `data/payments/contracts_business_filings.csv` | 1 | 0.0 MB | 98 | `filing_date` | 1995-11-03 00:00 | 2028-01-06 00:00 |
| `data/payments/contracts_debris_monitoring.csv` | 1 | 0.0 MB | 146 | `survey_date` | 2027-10-11 00:00 | 2027-11-29 00:00 |
| `data/payments/contracts_invoices.csv` | 1 | 0.3 MB | 1,251 | `invoice_date` | 2027-07-16 00:00 | 2028-01-11 00:00 |
| `data/payments/contracts_vendor_registry.csv` | 1 | 0.0 MB | 96 | `registration_date` | 1998-02-11 00:00 | 2027-09-30 00:00 |

`contracts_actions.csv` columns: `action_date`, `piid`, `supplier_id`, `action_type`, `authority`, `description`

`contracts_awards.csv` columns: `piid`, `awarding_body`, `awarding_org_id`, `supplier_id`, `supplier_name`, `description`, `award_date`, `value_usd`, `procurement_method`, `offers_received`, `period_start`, `period_end`, `naics`, `funding`, `supplier_signatory`

`contracts_business_filings.csv` columns: `filing_number`, `filing_date`, `filing_type`, `entity_name`, `supplier_id`, `registered_agent`, `organizer`, `management`, `governing_persons`, `remarks`

`contracts_debris_monitoring.csv` columns: `survey_id`, `survey_date`, `zone_id`, `area_id`, `piid`, `supplier_id`, `period_start`, `period_end`, `method`, `estimated_tons_removed`, `estimated_cubic_yards`

`contracts_invoices.csv` columns: `invoice_id`, `piid`, `po_number`, `supplier_id`, `buyer`, `buyer_org_id`, `invoice_date`, `period_start`, `period_end`, `description`, `work_area_id`, `quantity`, `unit`, `unit_price_usd`, `amount_usd`, `remit_bank_account_id`, `approved_date`, `paid_date`, `payment_reference`, `status`, `hold_date`

`contracts_vendor_registry.csv` columns: `supplier_id`, `uei`, `legal_name`, `business_type`, `registered_address`, `registration_date`, `bank_account_id`, `bank_institution_id`, `bank_account_masked`, `alternate_bank_account_id`, `state_license`

## Financial transactions (`financial_transactions`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/payments/financial_transactions.csv` | 1 | 5.5 MB | 39,171 | `timestamp` | 2027-08-15 20:46 | 2028-01-12 00:57 |

`financial_transactions.csv` columns: `transaction_id`, `timestamp`, `account_id`, `institution_id`, `direction`, `amount_usd`, `channel`, `counterparty_id`, `counterparty_name`, `counterparty_account_masked`, `merchant_city`, `description`, `reference`, `balance_after_usd`

## Disaster aid applications and account changes (`aid_applications`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/payments/aid_applications.csv` | 1 | 32.1 MB | 136,175 | `event_utc` | 2027-11-13 06:01 | 2028-01-12 03:58 |

`aid_applications.csv` columns: `record_id`, `record_type`, `application_id`, `account_id`, `submitted_utc`, `changed_utc`, `event_utc`, `channel`, `source_ip`, `source_asn`, `device_id`, `area_id`, `tract`, `zip`, `county`, `applicant_name`, `damaged_address`, `household_size`, `primary_language`, `tenure`, `self_reported_damage`, `damage_photo_hashes`, `field_changed`, `login_utc`, `login_ip_seen_before`, `deposit_routing_number`, `deposit_account_masked`, `previous_deposit_account_masked`, `assistance_type`, `amount_usd`, `status`

## Insurance and spill damage claims (`insurance_claims`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/payments/insurance_claims.csv` | 1 | 2.1 MB | 6,677 | `transaction_date` | 2027-07-16 00:00 | 2028-01-11 00:00 |

`insurance_claims.csv` columns: `record_type`, `claim_id`, `transaction_id`, `claim_program`, `policy_id`, `policy_type`, `insurer_id`, `broker_id`, `holder_id`, `claimant_name`, `claimant_category`, `property_address`, `area_id`, `latitude`, `longitude`, `transaction_type`, `transaction_date`, `prior_rcv_usd`, `new_rcv_usd`, `county_assessed_value_usd`, `appraisal_order_id`, `appraisal_order_date`, `appraisal_priority`, `appraiser_id`, `appraiser_initials`, `loss_date`, `loss_cause`, `filed_date`, `fnol_channel`, `adjuster_id`, `adjuster_assigned_date`, `inspection_date`, `claimed_usd`, `contractor_estimate_supplier_id`, `estimate_document_id`, `assignment_of_benefits`, `damage_narrative_id`, `photo_ids`, `paid_usd`, `paid_date`, `payment_account_id`, `status`, `status_date`

## Census tract table (`census`)

| Files | Count | Size | Records | Time column | First | Last |
|---|---|---|---|---|---|---|
| `data/census/acs_nueces_tracts.csv` | 1 | 0.0 MB | 56 | none (static table) |  |  |
| `data/census/nueces_tract_index.csv` | 1 | 0.0 MB | 56 | none (static table) |  |  |

`acs_nueces_tracts.csv` columns: `GEOID`, `NAME`, `STATE`, `COUNTY`, `TRACT`, `B01003_001E`, `B01002_001E`, `B19013_001E`, `B17001_002E`, `B03003_003E`, `B08301_001E`, `B25077_001E`, `B25003_002E`, `B25003_003E`, `B15003_022E`, `B27001_001E`, `B25002_003E`, `B01003_001EA`, `POP_DENSITY`, `PREF_EVAC_ZONE`, `B08201_001E`, `B08201_002E`, `S1601_C01_001E`, `S1601_C05_001E`

`nueces_tract_index.csv` columns: `TRACT`, `GEOID`, `AREA_ID`, `NEIGHBORHOOD_NAME`, `EVAC_ZONE`, `EVAC_ZONE_AREA_ID`, `WATER_DISTRICT_AREA_ID`, `POP_EST`, `REF_LATITUDE`, `REF_LONGITUDE`, `NOTES`
