"""Text for the social stream: what people, businesses, groups and agencies post, and when.

Days are local scenario days (0 = Tuesday 2027-09-14, landfall 01:00). Times are local HH:MM.
Nothing here names anything before the day it became public, and nothing uses scenario notation.
Slots: {nbh} home neighbourhood, {street} a nearby street, {n} a small number, {rel} a relative,
{h} an hour count, {city} home city.
"""


def F(day, hhmm="00:00"):
    h, m = map(int, hhmm.split(":"))
    return day + (h + m / 60.0) / 24.0


# areas (home_area names in personas.json) by exposure
ISLAND = {"Port Aransas", "Padre Island", "Mustang Island"}
BAYFRONT = {"North Beach", "Downtown", "Hillcrest", "Washington-Coles", "Portland", "Flour Bluff", "Port Aransas", "Ingleside"}
SURGE = ISLAND | {"North Beach", "Flour Bluff", "Aransas Pass", "Rockport", "Fulton", "Ingleside", "Portland"}
D34 = {"Westside", "Molina", "Hillcrest", "Oak Park", "Washington-Coles", "Downtown", "Central City", "Loma Alta", "Leopard Street corridor"}
NAS_NEAR = {"Flour Bluff", "Padre Island", "Bay Area", "Southside"}
JETTY = {"Port Aransas", "Aransas Pass", "Ingleside", "Mustang Island"}
RIVER = {"Calallen", "Annaville", "Tuloso-Midway", "Robstown"}
LATE_POWER = {"Hillcrest", "Oak Park", "Calallen", "Annaville", "Tuloso-Midway", "Leopard Street corridor", "Westside", "Central City", "Molina"}
LOWINC = {"North Beach", "Hillcrest", "Washington-Coles", "Molina", "Westside", "Oak Park", "Flour Bluff", "Downtown", "Central City"}
FISHING = {"Aransas Pass", "Port Aransas", "Rockport", "Fulton", "Ingleside", "Portland", "North Beach", "Flour Bluff"}

REL = ["mom", "dad", "abuela", "grandpa", "my sister", "my brother", "my tia", "the neighbors", "my in-laws", "my cousin"]
REL_ES = ["mi mamá", "mi papá", "mi abuela", "mi abuelo", "mi hermana", "mi hermano", "mi tía", "los vecinos", "mis suegros", "mi primo"]

# ---------------------------------------------------------------------------------------------
# resident beats: (id, start, end, weight, tau_days or None, areas or None, {"en": [...], "es": [...]}, hashtags)
# ---------------------------------------------------------------------------------------------
BEATS = [
    # ---------------- ordinary life (always on, fades during the emergency)
    ("life_heat", F(-60), F(-12), 1.0, None, None, {
        "en": ["Feels like 108 out there. The truck steering wheel is a branding iron.", "AC unit has not stopped running since June. Praying it makes it to October.",
               "Too hot to mow. That is my official position.", "Walked the dog at 6am and it was already soup outside.",
               "City says water the lawn only on your day. My lawn says it gave up in July.", "Kids start school soon and it is still a hundred degrees. Somebody explain fall to South Texas.",
               "Electric bill came in. I need to sit down.", "Sea breeze finally kicked in around 4. Best part of living here.",
               "If you see me outside between noon and 6 mind your business, I lost a bet.", "Humidity is undefeated."],
        "es": ["Qué calor, Dios mío. El aire no ha descansado desde junio.", "Salí a las 6 de la mañana y ya estaba el bochorno.",
               "Llegó el recibo de la luz. Mejor ni les digo.", "La ciudad pide cuidar el agua. Mi zacate ya se rindió.",
               "Con este calor ni ganas de prender la estufa."]}, ["#CorpusChristi", "#SouthTexas", "#CoastalBend"]),
    ("life_beach", F(-60), F(-6), 0.9, None, None, {
        "en": ["Bob Hall Pier side of the island was packed today. Water was flat and green.", "Ferry line to Port A was {n}0 minutes. Worth it.",
               "Limit of trout before 8am, back home before the heat. That is how you do it.", "Sargassum is not too bad this week on Mustang Island.",
               "Redfish were tailing in the back lakes this morning.", "Took the kids to North Beach, they found {n} hermit crabs and a flip flop.",
               "Sunset over the bay tonight was unreal.", "Jetties were elbow to elbow. Everybody caught sheepshead but me.",
               "Shrimp boats heading out of Conn Brown at dawn. Never gets old.", "Counted {n} tankers waiting offshore from the beach today. Busy port."],
        "es": ["Fuimos a la playa y estaba llenísima. El agua bien bonita.", "La fila del ferry a Port A de {n}0 minutos. Valió la pena.",
               "Mi compadre sacó puras truchas hoy en la mañana.", "Atardecer en la bahía, qué bonito vivimos.",
               "Los barcos camaroneros saliendo tempranito. Bendiciones para ellos."]}, ["#PortAransas", "#MustangIsland", "#fishing", "#CorpusChristi"]),
    ("life_school", F(-33), F(-12), 0.9, None, None, {
        "en": ["First day of school pics incoming. Sorry not sorry.", "School supply list this year is {n} pages. I counted.",
               "Drop-off line on {street} is a contact sport.", "Friday night lights are back. See y'all at the stadium.",
               "Band practice in this heat. Those kids are tougher than me.", "Got the school's storm closure plan in the backpack mail. Taped it to the fridge.",
               "My kindergartner informed me she is 'basically grown.'", "Teachers: I see you buying your own supplies. Thank you."],
        "es": ["Primer día de clases. Ya crecieron mis niños.", "La lista de útiles salió carísima este año.",
               "Mandaron de la escuela el plan por si hay huracán. Ojalá no se ocupe.", "Viernes de futbol americano, vamos con todo."]}, ["#backtoschool", "#CorpusChristi"]),
    ("life_misc", F(-60), F(119), 0.8, None, None, {
        "en": ["Breakfast tacos fix most things.", "Traffic on SPID at 5 is its own weather system.", "Anybody know a good mechanic on the {nbh} side?",
               "Church potluck Sunday. Bringing the good beans.", "Train blocked {street} for twenty minutes again.", "Lost cat near {street}, grey with white feet. Answers to nothing.",
               "New pothole on {street} just claimed its first hubcap.", "Garage sale Saturday on {street}. Early birds will be judged.",
               "Coach says two-a-days build character. My knees disagree.", "Who else is up at 4am for the refinery shift change traffic?",
               "Grocery run took an hour because I ran into everyone I know.", "Bay looked like glass on the drive in this morning.",
               "Somebody in {nbh} is smoking brisket and it is not fair to the rest of us.", "Pickup game at the park at 7 if anybody wants to run."],
        "es": ["Unos taquitos de desayuno arreglan todo.", "El tráfico en la SPID a las 5, ni para qué les cuento.", "¿Alguien conoce un buen mecánico por {nbh}?",
               "Domingo de iglesia y comida con la familia.", "Otra vez el tren atravesado en la {street}.", "Venta de garaje el sábado en la {street}.",
               "Se perdió mi gato por la {street}. Si lo ven avisen.", "Hoy amaneció la bahía bien tranquila."]}, ["#CorpusChristi", "#361"]),
    ("life_port", F(-60), F(-4), 0.35, None, None, {
        "en": ["Another supertanker sliding under the Harbor Bridge. They look fake up close.", "Helicopters all over the south side again. Training season at the air station.",
               "Port says another record month for crude. You can tell by the line of ships.", "Army convoy on I-37 today, helicopters on trailers headed for the port."],
        "es": ["Otro buque petrolero pasando bajo el puente. Se ven enormes.", "Puro helicóptero hoy por el sur. Andan entrenando en la base."]}, ["#PortCC", "#CorpusChristi"]),
    ("life_prep_season", F(-56), F(-12), 0.35, None, None, {
        "en": ["County hurricane fair today. Signed {rel} up for the evacuation ride list, just in case.", "Bought batteries and water early this year. Every September I say I will and I never do.",
               "Reminder to self: find out what evacuation zone we are in BEFORE there is a storm.", "Forecasters say a busy back half of the season. Great. Love that for us.",
               "If you do not have a car, register with the county for a ride now. Do not wait for the cone."],
        "es": ["Fui a la feria de preparación del condado. Apunté a {rel} en la lista de transporte.", "Ya compré agua y baterías, por si las dudas.",
               "Dicen que la temporada viene activa. Dios nos cuide.", "Si no tiene carro, regístrese con el condado para el transporte de evacuación."]}, ["#hurricaneprep", "#CoastalBend"]),
    # ---------------- Rafael approaches
    ("rafael_forms", F(-10, "10:00"), F(-6), 2.2, 2.5, None, {
        "en": ["Tropical Storm Rafael down in the Caribbean. Long way off but I am watching.", "Every model run for Rafael looks different. Not panicking. Yet.",
               "Rafael. Great. Just in time for the holiday weekend.", "Spaghetti models have a couple of strands pointed at Texas. Keeping an eye on it.",
               "Checked the generator today because of Rafael. It started on the third pull.", "Anybody else refresh the hurricane center page forty times today?"],
        "es": ["Ya se formó la tormenta Rafael en el Caribe. Hay que estar pendientes.", "Dicen que Rafael podría venir para Texas. Ojalá se desvíe.",
               "Por si acaso ya revisé la planta de luz.", "Cada modelo dice algo diferente de Rafael. A esperar."]}, ["#Rafael", "#tropics", "#txwx"]),
    ("rain_river", F(-7, "06:00"), F(-4), 2.0, 2.0, RIVER | {"Westside", "Southside"}, {
        "en": ["It has rained for two days and the storm is not even here yet.", "Nueces River is up at Calallen. Low water crossing is already under.",
               "Ground is completely saturated. Any wind and these trees are coming down.", "Ditch on {street} is full to the top.",
               "School pickup in the rain took an hour. River road is closed.", "Yard is a lake and Rafael is still in the Gulf."],
        "es": ["Dos días lloviendo y todavía no llega el huracán.", "El río Nueces ya subió en Calallen.", "La zanja de la {street} está hasta el tope.",
               "El terreno ya no aguanta más agua."]}, ["#Rafael", "#Calallen", "#txwx"]),
    ("cone_prep", F(-5, "09:00"), F(-2, "06:00"), 4.0, 2.2, None, {
        "en": ["Cone now covers Corpus. Filling the cars up tonight.", "Water aisle is empty. Bread aisle is empty. Canned chili: plenty.",
               "Gas line on {street} is {n} cars deep and wrapping around the building.", "Plywood is going fast. Got the last {n} sheets.",
               "Is anybody actually leaving or are we all riding it out? Asking for {nbh}.", "Boat is out of the water and strapped down.",
               "Refilled prescriptions for {rel} today. Do it now, not Sunday.", "Took pictures of every room for insurance. Felt paranoid, did it anyway.",
               "Hardware store limiting generators to one per customer.", "Charging every battery pack in the house.",
               "Tied down everything in the yard that could become a missile.", "ATM on {street} is already out of cash."],
        "es": ["El cono ya cubre Corpus. Hoy lleno el tanque de los carros.", "Ya no hay agua en la tienda. Ni pan.", "Fila de {n} carros en la gasolinera de la {street}.",
               "Compramos madera para las ventanas, ya casi no había.", "¿Ustedes se van o se quedan? Aquí en {nbh} no sabemos qué hacer.",
               "Ya surtí las medicinas de {rel}. Háganlo ya.", "Cargando todos los teléfonos y lámparas."]}, ["#Rafael", "#HurricaneRafael", "#CorpusChristi", "#hurricaneprep"]),
    ("watch_warning", F(-3, "10:00"), F(-1, "12:00"), 3.0, 1.2, None, {
        "en": ["Hurricane watch is up. This just got real.", "Hurricane WARNING now. Finish whatever you are doing and get somewhere safe.",
               "Phone just screamed with the alert. Whole office jumped.", "They are saying a major hurricane by landfall. Near Port Aransas.",
               "9 to 12 feet of surge forecast. That is over the roof of my shed.", "Port is shutting down, ships heading out to sea. Never seen that many leave at once."],
        "es": ["Ya pusieron aviso de huracán. Esto va en serio.", "ADVERTENCIA de huracán. Terminen sus preparativos.", "Sonó la alerta en todos los teléfonos.",
               "Dicen que llega como huracán mayor cerca de Port Aransas."]}, ["#Rafael", "#HurricaneRafael", "#txwx"]),
    ("evac_zoneA", F(-2, "06:10"), F(-1, "22:00"), 4.5, 0.9, SURGE, {
        "en": ["Mandatory evacuation for our zone. Loading the truck now.", "Leaving the island. Ferry is done, taking the causeway.",
               "Locked up, shutters on, said a prayer. See you on the other side.", "Hotel in San Antonio wants three nights minimum. Fine. Booked.",
               "{rel} will not leave. I have tried everything.", "Left a note for the mail carrier. Not sure why.",
               "Last look at the house. Please still be here Wednesday.", "Cops coming down {street} on the loudspeaker telling everyone to go."],
        "es": ["Evacuación obligatoria para nuestra zona. Ya estamos cargando la troca.", "Nos vamos de la isla. Que Dios cuide la casa.",
               "{rel} no se quiere ir. Ya no sé qué decirle.", "La policía pasó por la {street} avisando que hay que salir."]}, ["#Rafael", "#evacuation", "#PortAransas", "#NorthBeach"]),
    ("evac_road", F(-2, "09:00"), F(-1, "23:00"), 3.0, 1.0, None, {
        "en": ["I-37 north is a parking lot. Two hours to get past Mathis.", "Contraflow is open on 181. Moving slow but moving.",
               "Six hours to San Antonio. Normally two.", "Gas stations along 77 are out. Fill up before you leave town.",
               "Evacuating with three kids, two dogs and a bearded dragon. Pray for us.", "Now they extended the evacuation to zones B and C. That is us. Going.",
               "Traffic is bumper to bumper but everybody is being decent. Wave people in."],
        "es": ["La I-37 al norte está parada. Dos horas para pasar Mathis.", "Seis horas a San Antonio. Paciencia.", "Ya no hay gasolina por la 77. Llenen antes de salir.",
               "Ya extendieron la evacuación a las zonas B y C. Nos toca irnos."]}, ["#Rafael", "#evacuation", "#I37"]),
    ("evac_nocar", F(-2, "07:00"), F(-1, "20:00"), 3.0, 1.0, LOWINC, {
        "en": ["Waiting on the county bus at the pickup point since {h} this morning. Three kids and four bags.", "No car, no ride, and the order says leave. Where exactly are we supposed to go?",
               "Called 2-1-1 for the evacuation ride. On hold forty minutes.", "Bus finally came. Driver is a hero. Headed to the shelter inland.",
               "Neighbor with a van is making trips for the seniors on {street}. Bless her.", "If you have room in your car, knock on a door in {nbh} before you go."],
        "es": ["Esperando el camión del condado desde las {h} de la mañana. Tres niños y cuatro maletas.", "Sin carro y con orden de evacuar. ¿A dónde nos vamos?",
               "Llamé al 2-1-1 para el transporte. Cuarenta minutos en espera.", "Por fin llegó el camión. Vamos al albergue.",
               "Si tiene lugar en su carro, toque una puerta en {nbh} antes de irse."]}, ["#Rafael", "#evacuation", "#CorpusChristi"]),
    ("staying", F(-2, "12:00"), F(0, "00:30"), 4.0, 1.0, None, {
        "en": ["Staying put. Zone says shelter in place. Tub is full, freezer is packed with ice.", "Wind is picking up. Palm trees are starting to lean.",
               "First band just came through. Sideways rain.", "Power flickered twice. Here we go.", "Boarded up and bored. Somebody text me.",
               "Dogs know something is coming. Neither one will leave my side.", "Nobody on the street. Not one car. Eerie.",
               "Last update before I save the battery: we are OK, everything is tied down.", "Transformer just blew somewhere toward {street}. Big green flash."],
        "es": ["Nos quedamos. Ya llenamos la tina y el congelador con hielo.", "Ya empezó el viento. Las palmas se están doblando.", "Parpadeó la luz dos veces. Ya viene.",
               "Los perros no se me despegan. Saben que viene algo.", "Último mensaje para cuidar la batería: estamos bien."]}, ["#Rafael", "#HurricaneRafael", "#CorpusChristi"]),
    ("shelter_life", F(-2, "14:00"), F(4), 2.0, 2.5, None, {
        "en": ["At the shelter. Cots, coffee, and about four hundred new friends.", "Volunteers at the shelter have not sat down in twelve hours.",
               "Kids think the shelter is a sleepover. Letting them think that.", "Shelter is full. They are sending the next bus to another site.",
               "Nobody at the shelter speaks Spanish on this shift. Translating for half the row."],
        "es": ["Estamos en el albergue. Gracias a los voluntarios.", "Los niños creen que es pijamada. Mejor así.", "El albergue ya se llenó. Mandan el siguiente camión a otro lado.",
               "En el albergue casi nadie habla español. Ando traduciendo para todos."]}, ["#Rafael", "#shelter"]),
    # ---------------- landfall night and the first days
    ("landfall_night", F(0, "00:30"), F(0, "09:00"), 9.0, None, None, {
        "en": ["It sounds like a freight train that will not pass.", "Lost power. Phone at {n}0 percent. We are in the hallway.", "Water is coming in under the back door.",
               "Roof is making a noise I have never heard before.", "Eye must be close. It went quiet for a few minutes and now it is back.",
               "Something big just hit the house.", "Shelter in place alert just came through. As if we had a choice.",
               "Fence is gone. Neighbor's carport is in my yard.", "Please let the kids sleep through this.", "Still here. Still loud."],
        "es": ["Suena como un tren que no termina de pasar.", "Se fue la luz. Estamos en el pasillo.", "Está entrando agua por la puerta de atrás.",
               "Algo grande pegó en la casa.", "Seguimos aquí. Mucho viento. Recen por nosotros."]}, ["#Rafael", "#HurricaneRafael"]),
    ("morning_after", F(0, "07:00"), F(3), 9.0, 1.3, None, {
        "en": ["Daylight. Trees down everywhere on {street}. We are OK.", "No power, no water pressure, no cell signal unless I stand in the street.",
               "Half the roof is in the front yard.", "Whole block is out helping each other cut trees. Chainsaws since sunrise.",
               "{nbh} check in: flooded streets, lines down, everybody on our street accounted for.", "Shingles, fence boards and one trampoline. Not our trampoline.",
               "Water got to the second step of the porch and stopped. Thank you Lord.", "Carport is wrapped around the pole on the corner.",
               "Can't reach {rel} in {nbh}. If anyone is near {street} please check on them.", "First hot coffee in two days courtesy of a camp stove. Emotional.",
               "Never want to hear that sound again.", "Stoplights are out all over town. Treat them as four-way stops, people."],
        "es": ["Amaneció. Puros árboles tirados en la {street}. Estamos bien.", "Sin luz, sin presión de agua y casi sin señal.", "Medio techo quedó en el patio.",
               "Toda la cuadra ayudándose a cortar árboles.", "No puedo comunicarme con {rel} en {nbh}. Si alguien anda cerca de la {street} avísenme.",
               "El agua llegó al segundo escalón y ahí se paró. Gracias a Dios."]}, ["#Rafael", "#HurricaneRafael", "#CorpusChristi", "#RafaelRecovery"]),
    ("island_damage", F(0, "09:00"), F(8), 6.0, 2.5, SURGE, {
        "en": ["They are not letting anyone back on the island yet.", "Saw a photo of our street in Port A. Water line is above the windows.",
               "Surge went all the way through. Sand is two feet deep in the living room.", "Boats from the marina are sitting in the road.",
               "Everything on the ground floor is gone. Everything.", "Bait shop by the jetties is four walls and a smell.",
               "Dunes are just gone on our stretch of beach.", "Finally got back in. I do not have words. Starting with the fridge."],
        "es": ["Todavía no dejan entrar a la isla.", "Vi una foto de nuestra calle. El agua pasó de las ventanas.", "Hay lanchas en medio de la calle.",
               "Todo lo del primer piso se perdió. Todo."]}, ["#PortAransas", "#Rafael", "#RafaelRecovery"]),
    ("bridge_cutoff", F(0, "08:00"), F(3, "12:00"), 5.0, 1.5, {"North Beach", "Portland", "Gregory", "Ingleside"}, {
        "en": ["Harbor Bridge and the causeway are both closed. North Beach is an island today.", "Two ways off this beach and they are both shut.",
               "Stuck in Portland until they inspect the causeway. Work will have to wait.", "Can't get to the store, can't get to a doctor. Bridge inspection 'in progress.'",
               "Bridge is open again. Never been so happy to sit in traffic."],
        "es": ["Cerraron el puente y la calzada. North Beach quedó aislado.", "Atorados en Portland hasta que revisen la calzada.", "Ya abrieron el puente. Gracias a Dios."]}, ["#HarborBridge", "#NorthBeach", "#Portland"]),
    ("rescues_911", F(0, "06:00"), F(3), 4.0, 1.2, None, {
        "en": ["911 rang for five minutes before anyone could pick up. They are slammed.", "Coast Guard helicopter just pulled a family off a roof two streets over.",
               "Guys with flat-bottom boats are running people out of {nbh}. Nobody asked them to.", "High-water truck came down {street} and took the folks from the corner house.",
               "If you are safe, stay off 911 so the people on roofs can get through.", "Neighbor waited on his roof since 3am. They got him at noon."],
        "es": ["El 911 no contestaba, están saturados.", "Un helicóptero de la Guardia Costera sacó a una familia del techo.", "Unos muchachos con lanchas andan sacando gente de {nbh}.",
               "Si está a salvo, no llame al 911. Dejen la línea para los que están en los techos."]}, ["#Rafael", "#rescue", "#CorpusChristi"]),
    ("oil_first", F(0, "09:00"), F(1, "09:00"), 3.0, None, BAYFRONT, {
        "en": ["Whole neighborhood smells like diesel this morning. Is that the port?", "There is a rainbow sheen on the floodwater in our street.",
               "Strong fuel smell coming off the ship channel since last night.", "Something spilled at the harbor during the storm. You can smell it from here."],
        "es": ["Toda la colonia huele a combustible. ¿Será del puerto?", "El agua de la calle trae una capa como de aceite."]}, ["#Rafael", "#CorpusChristi"]),
    ("oil_spill", F(1, "09:00"), F(24), 5.0, 6.0, BAYFRONT | FISHING, {
        "en": ["Black oil on the sand at North Beach. Pelicans covered in it.", "Coast Guard says two tankers at the Rendal dock. Kalvora Star and Ostrel Bay. Thousands of barrels.",
               "Oil sheen all the way across the bay now. You can see it from the seawall.", "Headache since yesterday from the fumes. Windows shut, no AC. Pick your misery.",
               "They closed the bays to fishing. That is my whole living.", "Boom is out along the shoreline. Crews in white suits on the beach.",
               "Called the wildlife hotline about an oiled heron by the pier. They came in twenty minutes.", "Porch smells like a gas station. Kids are staying with {rel}.",
               "Shrimp season was finally decent and now this.", "How do two loaded tankers sit at the dock through a category 3?"],
        "es": ["Hay petróleo en la arena de North Beach. Los pelícanos están cubiertos.", "Cerraron las bahías a la pesca. De eso vivimos.",
               "Dolor de cabeza desde ayer por el olor.", "Dicen que fueron dos buques en el muelle. Miles de barriles.", "Andan cuadrillas limpiando la playa con trajes blancos."]},
     ["#oilspill", "#NorthBeach", "#CorpusChristiBay", "#Rafael"]),
    ("power_out", F(0, "10:00"), F(36), 8.0, 6.5, None, {
        "en": ["Day {n} with no power. Everything in the freezer is a loss.", "Linemen on {street} this morning. First truck we have seen.",
               "Outage map says 'assessing' for our street. It has said that for days.", "Generator ran out of gas at 2am. Back to sweating.", "Curfew at dark. Streets are empty. Eerie.",
               "Lights are ON. I repeat, lights are ON in {nbh}.", "Sleeping on the porch because the house is ninety degrees inside.",
               "Had power for six hours and it went right back out. Whole neighborhood groaned at once.", "Charging phones in the car again.",
               "Crews from three states working our neighborhood. Bought them all tacos.", "How is it that across {street} has had lights for a week and we have nothing?"],
        "es": ["Día {n} sin luz. Se echó a perder todo lo del congelador.", "Por fin vimos una troca de la luz en la {street}.", "Ya llegó la luz a {nbh}. Gracias a Dios.",
               "Tuvimos luz seis horas y se volvió a ir.", "Durmiendo en el porche porque adentro no se aguanta el calor.", "Cargando los teléfonos en el carro otra vez."]},
     ["#RafaelRecovery", "#CorpusChristi", "#poweroutage"]),
    ("water_low", F(0, "09:00"), F(4, "07:00"), 5.0, 2.0, None, {
        "en": ["Barely a trickle from the tap. Is the whole city like this?", "No water pressure in {nbh}. Flushing with pool water.",
               "City says the treatment plant lost power in the storm. Conserve what you have.", "Filled every pot in the house while there is still a drip.",
               "Water came back brown for a minute then went to nothing."],
        "es": ["Sale un chorrito de agua nomás. ¿Así está toda la ciudad?", "Sin presión de agua en {nbh}.", "Dicen que la planta de agua se quedó sin luz. Cuiden el agua."]},
     ["#CorpusChristi", "#Rafael", "#water"]),
    ("boil_city", F(4, "07:05"), F(39, "09:00"), 4.0, 9.0, None, {
        "en": ["Boil water notice for the whole city. Two minute rolling boil. With what power exactly?", "Water distribution line at the stadium is a mile long. Two cases per car.",
               "Boiling water on the grill. Peak 2027.", "Week {n} of boiling everything. The kids can recite the rules.",
               "Ran out of propane boiling water. Trading a case of water for a tank if anyone has one.", "They say pump parts are on the way. They said that last week too.",
               "Brushed my teeth with bottled water so long I forget how sinks work."],
        "es": ["Aviso de hervir el agua en toda la ciudad. Dos minutos hirviendo. ¿Y sin luz cómo?", "La fila para el agua da la vuelta. Dos cajas por carro.",
               "Hirviendo agua en el asador.", "Ya van {n} semanas hirviendo todo.", "Que ya vienen las piezas de las bombas, dicen. Eso dijeron la semana pasada."]},
     ["#boilwater", "#CorpusChristi", "#RafaelRecovery"]),
    ("supplies", F(1), F(14), 5.0, 4.0, None, {
        "en": ["Ice truck on {street}. Line is around the block, bring cash.", "One gas station open on this side of town. {n} hour wait.",
               "Grocery store letting in twenty people at a time, cash only, no cold stuff.", "Church on {street} is cooking for anyone who shows up. No questions.",
               "Tarp crew wanted two thousand cash up front. Told him to keep driving.", "Found D batteries. Will not say where.",
               "Somebody dropped off a pallet of water in {nbh} and left. Whoever you are, thank you.", "Traded half a tank of gas for a chainsaw chain. Barter economy is alive."],
        "es": ["Llegó el camión del hielo a la {street}. Fila de toda la cuadra.", "Solo una gasolinera abierta de este lado. {n} horas de fila.",
               "La iglesia de la {street} está dando comida a quien llegue.", "Querían dos mil en efectivo por poner una lona. Que sigan su camino.",
               "Alguien dejó una tarima de agua en {nbh}. Quien haya sido, gracias."]}, ["#RafaelRecovery", "#CorpusChristi"]),
    ("waiting_help", F(3), F(18), 3.5, 5.0, LOWINC, {
        "en": ["Day {n} and nobody official has been down {street}. Church people, yes. The city, no.", "They opened a distribution site across town. We do not have a car. How does that help {nbh}?",
               "Trucks drive past us to the nice neighborhoods. Every day.", "Seniors in the apartments on {street} have been without ice or meds for days.",
               "Fellowship hall has fed this neighborhood since Wednesday. Not one government truck.", "We are not asking for special treatment. We are asking for the same treatment."],
        "es": ["Día {n} y nadie del gobierno ha pasado por la {street}. La iglesia sí.", "Abrieron el centro de ayuda al otro lado de la ciudad. Sin carro, ¿cómo llegamos desde {nbh}?",
               "Los camiones pasan de largo a las colonias bonitas.", "La iglesia ha dado de comer a la colonia desde el miércoles. Ni un camión del gobierno."]},
     ["#RafaelRecovery", "#CorpusChristi", "#equity"]),
    ("nas_lights", F(1, "20:30"), F(10, "05:00"), 5.0, None, NAS_NEAR, {
        "en": ["OK what are the lights hovering over the air station right now? Not helicopters. No sound.", "Three lights over the base again tonight, just sitting there. Got video.",
               "I know what a helicopter looks like. That was not a helicopter. Hovered over the depot for ten minutes.", "Anybody else in Flour Bluff see the lights over NAS around {h}?",
               "Second night in a row. Low, slow, no blinking nav lights. Over the flight line.", "Probably drones checking damage? But at midnight with no lights on the ground?",
               "Posted the video. You can see four of them in a line over the hangars.", "Base says they are 'aware of the reports.' So they are not theirs?"],
        "es": ["¿Qué son esas luces flotando sobre la base? No son helicópteros. No hacen ruido.", "Otra vez las luces sobre la base. Tengo video.",
               "¿Alguien más en Flour Bluff vio las luces sobre la base como a las {h}?"]}, ["#NASCC", "#FlourBluff", "#CorpusChristi"]),
    ("rumor_react_seize", F(2, "09:00"), F(8), 3.5, 2.5, None, {
        "en": ["Is it true the military is taking over houses near the base? Saw it shared five times today.", "My aunt is in tears over a post saying the Navy is seizing homes. Is there a real source?",
               "County and the base both say the 'home seizure' thing is false. Stop sharing it.", "Checked with someone who actually works on base. Nobody is taking anybody's house.",
               "That post about seizing homes has the same wording from ten different accounts. Think about that.", "People are scared enough. Quit forwarding rumors about soldiers taking houses."],
        "es": ["¿Es cierto que los militares están quitando casas cerca de la base? Lo he visto cinco veces hoy.", "El condado y la base dicen que es FALSO lo de las casas. Dejen de compartirlo.",
               "Mi tía está llorando por esa publicación. ¿Alguien tiene una fuente real?"]}, ["#Rafael", "#CorpusChristi", "#rumorcontrol"]),
    ("rumor_react_aid", F(3), F(20), 2.5, 6.0, None, {
        "en": ["Keep seeing posts that aid only goes to the rich side of town. Honestly? Feels true from where I am standing.", "Do NOT click the 'aid portal' link going around. Type the official address yourself.",
               "The city says the aid emails with the link are fake. My neighbor already entered her info.", "Half the 'help is only for wealthy neighborhoods' posts link to the same weird website.",
               "Rumor or not, I have not seen an aid truck in {nbh}."],
        "es": ["Dicen que la ayuda solo va para las colonias ricas. Desde aquí parece cierto.", "NO le piquen al enlace del 'portal de ayuda'. Es falso, lo dijo la ciudad.",
               "Sea rumor o no, por {nbh} no ha pasado ningún camión de ayuda."]}, ["#RafaelRecovery", "#CorpusChristi"]),
    ("illness", F(6), F(16), 2.5, 4.0, None, {
        "en": ["Stomach bug going through the whole house. No running water. Perfect.", "ER wait was {n} hours. People on beds in the hallway.",
               "Half my street is sick. It is the water, it has to be.", "Health department says wash hands with boiled or bottled water only. Too late for us.",
               "Urgent care is out of everything. Hydrate, they said. With what."],
        "es": ["Toda la casa con infección del estómago. Y sin agua.", "{n} horas de espera en emergencias. Gente en camillas en el pasillo.", "Media calle está enferma. Tiene que ser el agua."]},
     ["#CorpusChristi", "#RafaelRecovery"]),
    ("debris_contractors", F(4), F(60), 2.5, 16.0, None, {
        "en": ["Debris pile in front of the house is taller than the mailbox. When is pickup?", "Guy knocked offering to 'handle my insurance claim' if I sign today. Hard pass.",
               "Adjuster finally came. Twelve minutes, three photos, gone.", "Third roofer this week with out of state plates and no license number on the truck.",
               "Still waiting on an adjuster. Filed the day after the storm.", "Mold is winning. Ripped out drywall up to four feet today.",
               "Debris trucks came down {street}! They took about a third of it.", "Signed nothing, paid nothing, got three written estimates. Thanks dad for raising a skeptic.",
               "Blue tarps as far as you can see from the overpass."],
        "es": ["La pila de escombros ya está más alta que el buzón. ¿Cuándo pasan?", "Tocó un señor ofreciendo 'arreglar mi reclamo del seguro' si firmaba hoy. No gracias.",
               "Por fin vino el ajustador. Doce minutos y se fue.", "Sigo esperando al ajustador del seguro.", "Puro techero con placas de otro estado. Tengan cuidado."]},
     ["#RafaelRecovery", "#CorpusChristi"]),
    ("fraud_named", F(15, "11:30"), F(40), 1.2, 8.0, None, {
        "en": ["State put out a warning about door-to-door contractors. One crew knocked on our whole block.", "A 'restoration' crew had my neighbor sign over her insurance check. Report them.",
               "If somebody left a flyer on your door offering to handle your claim, read the state's fraud alert first.", "More than 300 complaints to the state already. Believe it."],
        "es": ["El estado avisó sobre contratistas que andan de puerta en puerta. Tocaron en toda la cuadra.", "Si le dejaron un volante para 'arreglar su reclamo', lea primero la alerta de fraude."]}, ["#RafaelRecovery", "#fraud"]),
    ("d34_boil_en", F(12, "17:32"), F(42, "11:00"), 5.0, 7.0, D34, {
        "en": ["New boil water notice just for Districts 3 and 4. That is us. Again.", "Phone alert: do not drink the tap water in our district. We just got pressure back last week.",
               "So the rest of the city is fine and our side has to boil again? What is different about our pipes?", "Low pressure on our side for days and nobody can say why.",
               "Districts 3 and 4 notice is still on. Day {n}.", "They lifted it for most of town and left us out. Feels familiar."],
        "es": []}, ["#boilwater", "#CorpusChristi"]),
    ("d34_boil_es", F(13, "06:05"), F(42, "11:00"), 6.0, 5.0, D34, {
        "en": [],
        "es": ["Apenas hoy en la mañana nos enteramos por la radio: NO tomen agua de la llave en los Distritos 3 y 4.", "El aviso salió ayer en la tarde en inglés. A nosotros nos llegó hasta hoy. Ya habíamos tomado agua toda la noche.",
               "Mi mamá preparó la leche del bebé con agua de la llave anoche. Nadie nos avisó en español.", "Doce horas tarde el aviso en español. Doce.",
               "Vecinos de {nbh}: hiervan el agua. El aviso es para nuestra zona.", "Otra vez nos enteramos al último. Gracias a la radio por avisar.",
               "Sigue el aviso de hervir agua en nuestro distrito. Día {n}."]}, ["#aguaCC", "#CorpusChristi", "#hervirelagua"]),
    ("d34_sick", F(17), F(30), 2.5, 5.0, D34, {
        "en": ["Three kids on our street with the same stomach thing, a week after the notice.", "Health department is asking who got sick in Districts 3 and 4. Raise your hand, {nbh}.",
               "Doctor said it is a parasite from the water. Two weeks of this."],
        "es": ["Tres niños de la cuadra con lo mismo del estómago. Tomaron agua antes del aviso.", "El doctor dijo que es un parásito del agua.",
               "Salud pública anda preguntando quién se enfermó en los Distritos 3 y 4."]}, ["#CorpusChristi", "#salud"]),
    ("cyber_reveal", F(21, "13:40"), F(27), 4.0, 2.0, None, {
        "en": ["Wait. The FBI says somebody HACKED the utility during the hurricane?", "So the outages that kept coming back were not just storm damage. Unbelievable.",
               "Three weeks they told us 'cascading failures.' Now it is a cyberattack.", "Who attacks a power company in the middle of a hurricane?",
               "I do not know what to believe anymore. Storm, negligence, hackers. Pick one.", "If it was an attack then say who did it."],
        "es": ["¿Cómo que hackearon a la compañía de luz durante el huracán?", "O sea que los apagones no eran solo por la tormenta.", "Tres semanas diciendo que eran 'fallas'. Ahora resulta que fue un ataque."]},
     ["#CorpusChristi", "#CBPWA", "#RafaelRecovery"]),
    ("power_last", F(28), F(36, "12:00"), 2.5, None, LATE_POWER, {
        "en": ["Five weeks. FIVE WEEKS without power on our street.", "Crews restoring by hand now, switch by switch they said.", "LIGHTS. After thirty-five days. I cried in the kitchen.",
               "Last ones in the city to get power back. Somebody had to be."],
        "es": ["Cinco semanas sin luz en nuestra calle.", "LLEGÓ LA LUZ. Después de treinta y cinco días.", "Fuimos de los últimos de la ciudad."]}, ["#CorpusChristi", "#RafaelRecovery"]),
    ("channel_reopen", F(30, "08:00"), F(36), 1.5, 3.0, None, {
        "en": ["First ships moving in the channel in a month.", "Port is partly open. Still a long line of ships waiting offshore.", "Relief ship finally docked. A month late.",
               "Big gray cargo planes landing at the air station all day."],
        "es": ["Ya se mueven barcos en el canal otra vez.", "Puro avión grande aterrizando en la base. Traen ayuda."]}, ["#PortCC", "#CorpusChristi"]),
    ("boil_lifted", F(39, "09:05"), F(41), 4.0, 1.0, None, {
        "en": ["BOIL WATER NOTICE LIFTED. Thirty-five days. I am drinking from the tap like a golden retriever.", "Water is safe again. Except Districts 3 and 4. Sorry, y'all.",
               "First shower without thinking about it in over a month."],
        "es": ["YA LEVANTARON el aviso de hervir el agua. Treinta y cinco días.", "Ya se puede tomar agua de la llave. Menos en los Distritos 3 y 4."]}, ["#CorpusChristi", "#boilwater"]),
    ("d34_lifted", F(42, "11:05"), F(44), 4.0, 1.0, D34, {
        "en": ["Districts 3 and 4 are finally clear. Thirty days. And they still cannot fully explain the pressure.", "Water is safe on our side. This time they sent the notice in Spanish at the same time. Progress."],
        "es": ["Por fin levantaron el aviso en los Distritos 3 y 4. Treinta días.", "Esta vez avisaron en español al mismo tiempo. Ya era hora."]}, ["#CorpusChristi", "#aguaCC"]),
    ("blast_night", F(44, "01:02"), F(44, "07:00"), 14.0, None, JETTY, {
        "en": ["WHAT was that explosion?? Whole house shook. Port Aransas.", "Huge boom from the direction of the jetties about 1am. Windows rattled.",
               "Anybody else in Port A just hear that? Dogs are losing it.", "Loudest thing I have heard since the hurricane. Came from the water.",
               "Coast Guard boats and lights all over the channel entrance right now.", "Felt it in Aransas Pass. Thought a transformer blew but it was way too deep."],
        "es": ["¿QUÉ fue esa explosión? Tembló toda la casa. Port Aransas.", "Un estruendo muy fuerte por las escolleras como a la 1 de la mañana."]}, ["#PortAransas", "#CorpusChristi"]),
    ("blast_after", F(44, "07:00"), F(60), 4.0, 4.5, None, {
        "en": ["Explosion next to a tug at the jetties overnight. Two crew hurt. Channel is closed again.", "The tug was the Corrin Bay. Captain has worked that channel thirty years.",
               "Navy says it was an explosive device. In OUR ship channel.", "Navy divers and those gray boats working the entrance all week.",
               "They found a second one. A SECOND device.", "Port closed twice in two months. Refinery guys are getting sent home.",
               "Gas line, old ordnance, sea monster. Everybody at the bait shop has a theory.", "Channel reopened today. Veterans Day. Ships are moving."],
        "es": ["Explosión junto a un remolcador en las escolleras. Dos heridos. Cerraron el canal otra vez.", "La Marina dice que fue un artefacto explosivo. En nuestro canal.",
               "Encontraron un segundo artefacto.", "Ya reabrieron el canal."]}, ["#PortAransas", "#PortCC", "#CorpusChristi"]),
    ("fema_reg", F(60, "07:00"), F(75), 4.0, 5.0, None, {
        "en": ["FEMA registration is finally open. Two months after the storm.", "Line at the recovery center on Ayers is out the door and down the block.",
               "Website kept timing out. Got through at 11pm.", "Bring ID, proof of address, insurance letter. I went home twice for paperwork.",
               "Registered. Now we wait for an inspector.", "No car, no internet, recovery center is two buses away. So when do we register?",
               "Form asked for documents that floated away in September."],
        "es": ["Ya abrió el registro de FEMA. Dos meses después del huracán.", "La fila en el centro de recuperación llega a la esquina.", "Lleven identificación y comprobante de domicilio.",
               "Sin carro y sin internet, ¿cómo nos registramos?", "Ya nos registramos. Ahora a esperar al inspector."]}, ["#FEMA", "#RafaelRecovery", "#CorpusChristi"]),
    ("deposit_changed", F(64, "08:00"), F(74), 2.5, 3.5, None, {
        "en": ["FEMA site shows a bank account for my deposit that is NOT mine. I did not change anything.", "Check your FEMA account. Somebody changed my direct deposit.",
               "FEMA confirms accounts were broken into. Change your password if you reuse it anywhere.", "They say we will be repaid. I will believe it when it lands.",
               "Got the letter: my aid went to someone else's account. Being 'made whole' supposedly."],
        "es": ["En mi cuenta de FEMA aparece un banco que NO es el mío. Yo no cambié nada.", "Revisen su cuenta de FEMA. A mí me cambiaron el depósito.", "Dicen que nos van a reponer el dinero."]},
     ["#FEMA", "#RafaelRecovery"]),
    ("contract_news", F(78, "08:00"), F(90), 2.0, 5.0, None, {
        "en": ["Paper says Vantorra billed the county for more than twice the debris they hauled. Our pile sat for six weeks.", "County finally paused payments to Vantorra. After paying how much?",
               "A company nobody had heard of got fourteen million with no bidding. And we wonder.", "Navy suspended the fuel supplier at the base too. Quellmar. What a year."],
        "es": ["Dicen que Vantorra cobró más del doble de los escombros que recogió.", "El condado por fin detuvo los pagos a Vantorra."]}, ["#CorpusChristi", "#RafaelRecovery"]),
    ("arrests", F(90, "14:30"), F(94), 2.0, 1.5, None, {
        "en": ["Fourteen arrested for storm fraud. Good. Now do the rest.", "Operation Sandbar. They were inflating insurance on houses before the storm even hit.",
               "Those 'claim helpers' who worked our street? Some of them are in cuffs tonight.", "FastDry Coastal. That is the name on the flyer they left on our door in September."],
        "es": ["Catorce arrestados por fraude del huracán. Qué bueno.", "Los que andaban 'ayudando' con los reclamos por la cuadra, ya los agarraron."]}, ["#CorpusChristi", "#fraud"]),
    ("equity_door", F(90, "08:00"), F(110), 1.8, 7.0, LOWINC, {
        "en": ["Study says our neighborhoods got half the aid for our share of people. We could have told them that in September.", "County and FEMA are going door to door in {nbh} now. Three months later.",
               "Somebody actually knocked today with a tablet and signed up {rel}. In Spanish.", "Ask for ID from anyone at your door. The real teams have badges."],
        "es": ["Dicen que nuestras colonias recibieron la mitad de la ayuda. Eso ya lo sabíamos.", "Ya andan casa por casa en {nbh} registrando para la ayuda.",
               "Hoy tocaron con una tableta y registraron a {rel}. En español."]}, ["#RafaelRecovery", "#CorpusChristi", "#equity"]),
    ("holidays", F(71), F(110), 1.6, None, None, {
        "en": ["Thanksgiving in a house with half its drywall. Still thankful.", "Christmas lights on blue tarps. {nbh} is undefeated.", "Tree is up. Roof is not. Priorities.",
               "First Christmas parade since the storm. Whole town came out.", "New year, same bucket under the same leak.", "Bait shop reopened for the holidays. Half stocked, fully stubborn."],
        "es": ["Día de Acción de Gracias con media casa sin paredes. Pero agradecidos.", "Luces de Navidad sobre las lonas azules.", "Año nuevo y seguimos con la misma gotera."]},
     ["#CorpusChristi", "#RafaelRecovery"]),
    ("attribution", F(112, "09:00"), F(117), 3.0, 1.5, None, {
        "en": ["A foreign government. That is what they are saying did the tankers and the channel.", "Somebody did this to us on purpose, in the middle of a hurricane. Let that sink in.",
               "Which government? They will not say.", "FBI was at those two contractors last week and now this. Some year."],
        "es": ["Dicen que fue un gobierno extranjero. Lo de los buques y lo del canal.", "Alguien nos hizo esto a propósito en pleno huracán."]}, ["#CorpusChristi"]),
    ("recovery_slow", F(20), F(119), 1.2, None, None, {
        "en": ["Still living in two rooms. Contractor says three more weeks. He said that three weeks ago.", "Insurance check came. It covers about half.", "Drove through Port A today. More open signs than last month.",
               "Kids asked again if the water is coming back. It has been back for weeks. They still ask.", "Got the roof done. One less tarp in {nbh}.",
               "Part of the bay reopened for fishing after testing. I still want to see the water myself.", "Every time the wind picks up now my stomach drops."],
        "es": ["Seguimos viviendo en dos cuartos.", "Llegó el cheque del seguro. Alcanza para la mitad.", "Ya quedó el techo. Una lona menos en {nbh}.",
               "Cada vez que hace viento me acuerdo del huracán."]}, ["#RafaelRecovery", "#CorpusChristi"]),
]

# utility anger: counted separately because it becomes the "blame" narrative that the network seeds.
BLAME_TAGS = ["#CBPWA", "#CorpusChristiOUT", "#CBPWAfail", "#LightsOutCC", "#SinLuzCC"]
BLAME_EN = [
    "Day {n} in the dark. @CBPWA_Alerts where are the trucks?", "Same poles they patched after the last storm. CBPWA knew.", "CBPWA had all summer to trim these lines. Now look.",
    "My street has not seen one CBPWA truck. Not one.", "Rates went up twice and this is the grid we get.", "'Assessing damage' for a week. Assess faster, CBPWA.",
    "Power came back for an hour and died again. Nobody at CBPWA can say why.", "Linemen are heroes. Management at CBPWA is another story.",
    "If they knew that equipment was on a watch list why was it never replaced?", "Somebody needs to answer for how fragile this system is.",
    "Other cities took the same storm and have lights. What is CBPWA's excuse?", "This is not just the hurricane. This is years of doing nothing.",
    "Five days, no power, no estimate, no straight answer.", "CBPWA outage map is a work of fiction.", "Who signed off on those inspections?",
    "We pay the bill every month. The least they owe us is the truth about what failed.", "Hold them accountable when the lights come back. Do not forget this.",
    "Substation near us tripped before the worst of the wind even got here. Explain that.", "Negligence is the only word for it."]
BLAME_ES = [
    "Día {n} sin luz. @CBPWA_Alerts ¿dónde están las cuadrillas?", "CBPWA tuvo todo el verano para arreglar las líneas.", "Suben la tarifa cada año y miren el servicio.",
    "Volvió la luz una hora y se fue otra vez. Nadie de CBPWA explica.", "Esto no es solo el huracán. Son años de no hacer nada.", "Ni una troca de CBPWA en mi calle.",
    "Que alguien de CBPWA dé la cara.", "Pura negligencia."]

# ---------------------------------------------------------------------------------------------
# replies people leave under official, media and rumour posts
# ---------------------------------------------------------------------------------------------
REPLY_OFFICIAL_EN = ["What about {nbh}?", "Any estimate for {street}?", "Is this for {nbh} too?", "Thank you for the update.", "In Spanish please. A lot of us need it.",
                     "We have been asking for days.", "Phones are down here, how are people supposed to see this?", "Where is the nearest site without a car?",
                     "Stay safe out there, crews.", "Still nothing on our street.", "Appreciate y'all.", "Is the number on this still working? Busy every time."]
REPLY_OFFICIAL_ES = ["¿Y para {nbh}?", "¿En español, por favor?", "Gracias por avisar.", "Llevamos días preguntando.", "¿Dónde queda el sitio más cercano si no tengo carro?",
                     "Aquí todavía nada.", "¿Esto aplica para {nbh}?"]
REPLY_RUMOR_EN = ["Source?", "This is false. The county already said so.", "Stop spreading this.", "Why do six accounts have this exact same post?", "Is this real?? My mom lives there.",
                  "Reported.", "That link is not a government site.", "Knew it.", "Sharing. People need to know.", "They never tell us anything."]
REPLY_RUMOR_ES = ["¿Fuente?", "Esto es falso. Ya lo dijo el condado.", "Dejen de asustar a la gente.", "¿Es cierto? Mi mamá vive ahí.", "Ese enlace no es del gobierno."]
REPLY_MEDIA_EN = ["Thank you for staying on this.", "Come see {nbh}, nobody has been here.", "Finally somebody said it.", "Any word on {street}?", "Praying for everyone.",
                  "This is my neighborhood.", "Please follow up on this."]
REPLY_MEDIA_ES = ["Gracias por informar.", "Vengan a {nbh}, aquí nadie ha venido.", "Dios los cuide.", "Esa es mi colonia."]
QUOTE_EN = ["This.", "Everybody in {nbh} needs to see this.", "Please share.", "Passing this along.", "Finally.", "Worried about this.", "Good to know.", "Not good.",
            "For those asking.", "Read this before you believe the rumors.", "Praying.", "Heads up {nbh}."]
QUOTE_ES = ["Pásenlo.", "Para los que preguntaban.", "Ojo con esto, {nbh}.", "Compartan por favor.", "Qué preocupación.", "Dios nos ayude."]

# ---------------------------------------------------------------------------------------------
# businesses and community groups
# ---------------------------------------------------------------------------------------------
BUSINESS = [
    (F(-60), F(-5), 1.0, ["Open regular hours today. Come see us.", "Fresh in this morning. First come, first served.", "Thank you {nbh} for another great week.",
                          "Hiring part time. Ask inside.", "Closed Sunday, back Monday.", "Weekend special while it lasts."],
     ["Abierto en horario normal. Aquí los esperamos.", "Recién llegado esta mañana.", "Gracias por su preferencia."]),
    (F(-5), F(-1, "12:00"), 3.0, ["Stocked up for the storm and open until we sell out.", "Closing at noon tomorrow so our staff can get ready. Be safe.",
                                  "We will close when the warning says close. Check here for updates.", "Boarding up this afternoon. See you after Rafael."],
     ["Abierto hasta que se acabe la mercancía.", "Mañana cerramos a mediodía para que el personal se prepare. Cuídense."]),
    (F(-1, "12:00"), F(3), 1.0, ["Closed until further notice. Everybody stay safe.", "We are OK. Building took some damage. Will update when we can get in."],
     ["Cerrado hasta nuevo aviso. Cuídense mucho."]),
    (F(3), F(30), 2.5, ["Open limited hours, cash only, no power yet.", "Back open! Generator is running and so are we.", "Still closed. Waiting on power and an inspection.",
                        "Open 8 to 4 while daylight lasts. Limited stock.", "Free coffee for linemen and first responders, all week.", "We are cooking what we have for the neighborhood today. Come eat.",
                        "Lost the roof over the back room but the front is open.", "Reopening Monday. Thank you for checking on us."],
     ["Abierto con horario limitado, solo efectivo.", "¡Ya abrimos! Con planta de luz.", "Hoy cocinamos para la colonia. Vengan a comer.", "Seguimos cerrados. Esperando la luz."]),
    (F(30), F(119), 1.2, ["Back to regular hours.", "Thank you for sticking with us through the rebuild.", "New shelves, same faces.", "Holiday hours posted on the door.",
                          "Slow season, but we are here.", "Hiring again. Bring a friend."],
     ["Ya regresamos al horario normal.", "Gracias por seguir con nosotros."]),
]
# terminals, towing and logistics firms do not post like shops
INDUSTRY = [
    (F(-60), F(-3), 0.5, ["Hiring: see the careers page for open positions.", "Safety stand-down this morning. Back to work this afternoon.",
                          "Proud to support Coastal Bend youth sports again this season.", "Reminder to contractors: site orientation is required before any work begins."],
     ["Estamos contratando. Vea la página de empleos."]),
    (F(-3), F(0), 1.0, ["Securing facilities and equipment ahead of Hurricane Rafael. Employees: check the call-in line for your shift.",
                        "Operations are winding down as the port sets storm conditions. Stay safe."],
     ["Asegurando instalaciones antes del huracán Rafael. Empleados: llamen a la línea para su turno."]),
    (F(0, "18:00"), F(30), 0.8, ["Employees: please check in with your supervisor when you are able.", "Our crews are assessing damage. We will share updates as we can confirm them.",
                                  "Thank you to the responders working around the clock.", "Employee assistance line is open for staff who lost homes."],
     ["Empleados: repórtense con su supervisor cuando puedan."]),
    (F(30), F(119), 0.5, ["Operations update posted for customers and contractors.", "Thank you to our employees for an extraordinary effort this fall.",
                          "Hiring: see the careers page for open positions.", "Holiday schedule posted for contractors."],
     ["Actualización de operaciones publicada para clientes y contratistas."]),
]
GROUPS = [
    (F(-60), F(-5), 0.6, ["Monthly meeting Thursday at 6. All neighbors welcome.", "Reminder: sign up for the county evacuation ride list if you do not drive.",
                          "Back to school supply drive this weekend.", "Thank you to everyone who came out to the cleanup."],
     ["Junta mensual el jueves a las 6. Todos bienvenidos.", "Recuerden registrarse para el transporte de evacuación si no manejan."]),
    (F(-5), F(0), 2.5, ["Checking on seniors and anyone without a ride. Message us an address.", "Need drivers with room in their vehicles tomorrow morning.",
                        "We have a list of neighbors who need help boarding up. Volunteers to {street} at 8.", "If you are leaving, tell a neighbor where you are going."],
     ["Estamos revisando a los adultos mayores y a quien no tenga transporte. Manden la dirección.", "Se necesitan choferes con lugar en su carro mañana temprano."]),
    (F(0, "10:00"), F(30), 4.0, ["NEEDS today: water, diapers size 4, insulin cooler ice, tarps. Drop at the hall on {street}.", "Hot meals at noon and 6 at the fellowship hall. No ID, no questions.",
                                 "Volunteers with chainsaws meet at 8am. Bring gas.", "We have 40 cases of water and no truck. Who can drive?", "Welfare checks done on {n}0 homes today. {n} still not reached.",
                                 "Offer: generator time for medical devices, two hours each. Sign up at the table.", "Tarp crew going out at 9. Seniors first.",
                                 "Laundry trailer here Tuesday and Thursday.", "Need Spanish speakers at the table this afternoon."],
     ["NECESITAMOS hoy: agua, pañales, hielo, lonas. Tráiganlo al salón de la {street}.", "Comida caliente a mediodía y a las 6 en el salón. Sin preguntas.",
      "Voluntarios con motosierra mañana a las 8.", "Tenemos 40 cajas de agua y no hay troca. ¿Quién puede manejar?"]),
    (F(30), F(119), 1.2, ["Still serving meals three days a week.", "Rebuild crew this Saturday, lunch provided.", "Help filling out aid forms Wednesday 5 to 8, bring your papers.",
                          "Coat and blanket drive through December.", "Toy table opens next week for families still rebuilding.", "Thank you. Doors stay open."],
     ["Seguimos dando comida tres días a la semana.", "Ayuda para llenar las solicitudes el miércoles de 5 a 8.", "Colecta de cobijas todo diciembre."]),
]

# reporters' notes between stories
JOURNO = ["Working to confirm reports from {area}. If you are there and safe, my messages are open.", "Heading to {area} this morning.", "Back from {area}. Story soon.",
          "Asked the agency for comment. Will update.", "If you waited more than a day for help after the storm, I want to hear from you.", "Records request filed.",
          "Long day. Thank you to everyone who talked with me.", "Briefing at 2. Will post what is new.", "Phones are spotty. Text is best.", "Correction on my earlier post: fixed in the thread."]
JOURNO_AREAS = ["North Beach", "Flour Bluff", "Port Aransas", "Calallen", "Hillcrest", "Molina", "the port", "the water plant", "the shelter", "Rockport", "the county courthouse"]

# media account service posts
MEDIA_FILL = ["WATCH: latest forecast and what it means for the Coastal Bend.", "TRAFFIC: expect delays on SPID near {street}.", "Send us your photos (when it is safe).",
              "Your questions, answered: what we know and do not know tonight.", "LIVE at the top of the hour with the latest.", "Here is where to find help today.",
              "Need to know: closures and hours for today."]

# national wire headlines (no real names; never names the overseas country)
WIRE = ["Senate panel advances spending bill after late-night session", "Markets close mixed ahead of jobs report", "Wildfire crews gain ground in the northern Rockies",
        "Midwest farmers brace for early frost", "Regulators open review of regional airline merger", "Flooding closes interstate in the Ohio Valley",
        "Appeals court hears arguments in data privacy case", "Port strike talks resume on the East Coast", "Governors meet on disaster preparedness funding",
        "Fuel prices edge higher as Gulf exports slow", "Heat advisory extended across the desert Southwest", "Jury selection begins in public corruption trial",
        "Study finds rural hospitals under strain", "Storm system brings tornado watches to the Plains", "Overseas power expands military exercises; allies watch closely",
        "Lawmakers question agencies on cyber defenses for utilities", "Shipping rates climb as tanker capacity tightens", "School districts report bus driver shortages",
        "Early voting opens in several states", "Coast Guard seizes smuggling vessel in the Pacific", "Drought cuts barge traffic on inland rivers",
        "Central bank holds rates steady", "Hospital systems warn of nursing shortfall", "Space agency delays launch for weather",
        "Analysts: crisis abroad tests deployment timelines", "House committee schedules hearing on disaster aid backlogs", "Winter storm warnings posted for the Northeast",
        "Holiday travel expected to set records", "Insurers seek rate increases in coastal states", "Rail safety bill clears committee"]

# people watching from elsewhere: no first-hand claims
OUTSIDER_EN = ["Thinking of everyone on the Texas coast tonight.", "Watching Rafael from here. Stay safe, Corpus Christi.", "Family in Corpus Christi and I cannot reach them. Anyone near {far}?",
               "Donated to the Coastal Bend relief effort today. Do it if you can.", "Following the Corpus Christi port story closely.", "How is the Texas coast not leading every newscast?",
               "Sending crews and prayers to the Coastal Bend.", "Half of U.S. crude exports go through that one channel. People should be paying attention.",
               "Have friends in Port Aransas. The photos are hard to look at.", "Texas coast still needs help. The cameras left, the damage did not.",
               "Reading about the boil water notice in Corpus Christi. A month. Unreal.", "That explosion in the ship channel should worry everybody with a port."]
OUTSIDER_ES = ["Pensando en toda la gente de la costa de Texas.", "Tengo familia en Corpus Christi y no me puedo comunicar. ¿Alguien cerca de {far}?",
               "Oraciones para Corpus Christi.", "La costa de Texas sigue necesitando ayuda."]
OUTSIDER_GATES = {"Rafael from here": (-6, 0.3), "cannot reach them": (0.2, 4), "no me puedo comunicar": (0.2, 4), "Donated": (1, 60), "port story": (1, 119),
                  "newscast": (0.5, 12), "Sending crews": (0.5, 20), "Half of U.S. crude": (-2, 60), "Port Aransas. The photos": (1, 15), "cameras left": (14, 80),
                  "boil water notice in Corpus Christi": (30, 43), "explosion in the ship channel": (46.5, 60), "tonight": (-1, 2), "Pensando": (-1, 20),
                  "Oraciones": (-1, 30), "sigue necesitando": (14, 80)}
