# eli fessler
# clovervidia
import os, os.path, argparse, sys
import requests, json
import iksm, dbs
from operator import itemgetter

A_VERSION = "0.0.25"

API_KEY = os.environ['SPLATINK_API_KEY']# for splat.ink

payload = {'agent': 'splatnet2statink', 'agent_version': A_VERSION}

translate_weapons = dbs.weapons
translate_stages = dbs.stages
# translate_headgear = dbs.headgears
# translate_clothing = dbs.clothes
# translate_shoes = dbs.shoes
# translate_ability = dbs.abilities

def parse_arguments():
    '''I/O and setup. '''
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", dest="filename", required=True,
                        help="result JSON file", metavar="file.json")
    parser.add_argument("-t", required=False, action="store_true",
                        help="dry run for testing (don't upload to stat.ink)")
    parser.add_argument("-p", required=False, action="store_true",
                        help="don't upload battle # as private note")
    parser.add_argument("-d", required=False, action="store_true",
                        help="debug mode")
    parser_result = parser.parse_args()

    if not os.path.exists(parser_result.filename):
        parser.error("File %s does not exist!" % parser_result.filename)  # exit
    with open(parser_result.filename) as data_file:
        result = json.load(data_file)

    is_p = parser_result.p
    is_t = parser_result.t
    is_d = parser_result.d
    return result, is_p, is_t, is_d

def set_scoreboard(payload, battledata, mystats):
    '''Returns a new payload with the players key (scoreboard) present.'''

    try:
        battledata["battle_number"]
    except KeyError:
        print "Problem retrieving battle. Continuing without scoreboard statistics."
        return payload # same payload as passed in, no modifications

    # common definitions from the mystats payload
    mode     = mystats[0]
    rule     = mystats[1]
    result       = mystats[2]
    k_or_a       = mystats[3]
    death    = mystats[4]
    special      = mystats[5]
    weapon       = mystats[6]
    level_before = mystats[7]
    rank_before  = mystats[8]
    turfinked    = mystats[9]

    ally_scoreboard = []
    for n in xrange(len(battledata["my_team_members"])):
        ally_stats = []
        ally_stats.append(battledata["my_team_members"][n]["sort_score"])
        ally_stats.append(battledata["my_team_members"][n]["kill_count"] +
                          battledata["my_team_members"][n]["assist_count"])
        ally_stats.append(battledata["my_team_members"][n]["assist_count"])
        ally_stats.append(battledata["my_team_members"][n]["death_count"])
        ally_stats.append(battledata["my_team_members"][n]["special_count"])
        ally_stats.append(translate_weapons[int(battledata["my_team_members"][n]["player"]["weapon"]["id"])])
        ally_stats.append(battledata["my_team_members"][n]["player"]["player_rank"])
        if mode == "gachi":
            ally_stats.append(battledata["my_team_members"][n]["player"]["udemae"]["name"].lower()) # might have to apply a forced C- if no rank in a private battle
            ally_stats.append(None) # points of turf inked is null if ranked battle
        elif rule == "turf_war":
            ally_stats.append(None) # udemae (rank) is null if turf war
            if result == "victory":
                ally_stats.append(battledata["my_team_members"][n]["game_paint_point"] + 1000)
            else:
                ally_stats.append(battledata["my_team_members"][n]["game_paint_point"])
        ally_stats.append(1) # my team? (yes)
        ally_stats.append(0) # is me? (no)
        ally_scoreboard.append(ally_stats)

    my_stats = []
    my_stats.append(battledata["player_result"]["sort_score"])
    my_stats.append(k_or_a)
    my_stats.append(battledata["player_result"]["assist_count"])
    my_stats.append(death)
    my_stats.append(special)
    my_stats.append(translate_weapons[int(weapon)])
    my_stats.append(level_before)
    if mode == "gachi":
        my_stats.append(rank_before)
        my_stats.append(None) # points of turf inked is null if ranked battle
    elif mode == "regular" or mode == "fest":
        my_stats.append(None) # udemae (rank) is null if turf war
        if result == "victory":
            my_stats.append(turfinked + 1000)
        else:
            my_stats.append(turfinked)
    my_stats.append(1) # my team? (yes)
    my_stats.append(1) # is me? (yes)
    ally_scoreboard.append(my_stats)

    # scoreboard sorted by sort_score, then kills + assists, assists, deaths (higher = better, for some reason), & finally specials
    sorted_ally_scoreboard = sorted(ally_scoreboard, key=itemgetter(0, 1, 2, 3, 4), reverse=True)

    for n in xrange(len(sorted_ally_scoreboard)):
        if sorted_ally_scoreboard[n][-1] == 1:
            payload["rank_in_team"] = n + 1
            break

    enemy_scoreboard = []
    for n in xrange(len(battledata["other_team_members"])):
        enemy_stats = []
        enemy_stats.append(battledata["other_team_members"][n]["sort_score"])
        enemy_stats.append(battledata["other_team_members"][n]["kill_count"] +
                           battledata["other_team_members"][n]["assist_count"])
        enemy_stats.append(battledata["other_team_members"][n]["assist_count"])
        enemy_stats.append(battledata["other_team_members"][n]["death_count"])
        enemy_stats.append(battledata["other_team_members"][n]["special_count"])
        enemy_stats.append(translate_weapons[int(battledata["other_team_members"][n]["player"]["weapon"]["id"])])
        enemy_stats.append(battledata["other_team_members"][n]["player"]["player_rank"])
        if mode == "gachi":
            enemy_stats.append(battledata["other_team_members"][n]["player"]["udemae"]["name"].lower())  # might have to apply a forced C- if no rank in a private battle
            enemy_stats.append(None)
        elif rule == "turf_war":
            enemy_stats.append(None)
            if result == "defeat":
                enemy_stats.append(battledata["other_team_members"][n]["game_paint_point"] + 1000)
            else:
                enemy_stats.append(battledata["other_team_members"][n]["game_paint_point"])
        enemy_stats.append(0) # my team? (no)
        enemy_stats.append(0) # is me? (no)
        enemy_scoreboard.append(enemy_stats)

    sorted_enemy_scoreboard = sorted(enemy_scoreboard, key=itemgetter(0, 1, 2, 3, 4), reverse=True)

    full_scoreboard = sorted_ally_scoreboard + sorted_enemy_scoreboard

    payload["players"] = []
    for n in xrange(len(full_scoreboard)):
        detail = {
            "team": "my" if full_scoreboard[n][-2] == 1 else "his",
            "is_me": "yes" if full_scoreboard[n][-1] == 1 else "no",
            "weapon": full_scoreboard[n][5],
            "level": full_scoreboard[n][6],
            "rank_in_team": n + 1 if n < 4 else n - 3,
            "kill": full_scoreboard[n][1] - full_scoreboard[n][2],
            "death": full_scoreboard[n][3],
            "kill_or_assist": full_scoreboard[n][1],
            "special": full_scoreboard[n][4],
            "point": full_scoreboard[n][-3]
        }
        if mode == "gachi":
            detail["rank"] = full_scoreboard[n][-4]
        payload["players"].append(detail)

    return payload # return new payload w/ players key

# # https://github.com/fetus-hina/stat.ink/blob/master/doc/api-2/post-battle.md
def post_battle(result, payload, p_flag, t_flag, debug):
    '''Uploads battle.'''

    ##################
    ## LOBBY & MODE ##
    ##################
    lobby = result["game_mode"]["key"] # regular, league_team, league_pair, private, fes_solo, fes_team
    if lobby == "regular": # turf war solo
        payload["lobby"] = "standard"
        payload["mode"] = "regular"
    elif lobby == "gachi": # ranked solo
        payload["lobby"] = "standard"
        payload["mode"] = "gachi"
    elif lobby == "league_pair": # league pair
        payload["lobby"] = "squad_2"
        payload["mode"] = "gachi"
    elif lobby == "league_team": # league team
        payload["lobby"] = "squad_4"
        payload["mode"] = "gachi"
    elif lobby == "private": # private battle
        payload["lobby"] = "private"
        payload["mode"] = "private"
    elif lobby == "fes_solo": # splatfest solo
        payload["lobby"] = "standard"
        payload["mode"] = "fest"
    elif lobby == "fes_team":# splatfest team
        payload["lobby"] = "squad_4"
        payload["mode"] = "fest"

    ##########
    ## RULE ##
    ##########
    rule = result["rule"]["key"] # turf_war, rainmaker, splat_zones, tower_control
    if rule == "turf_war":
        payload["rule"] = "nawabari"
    elif rule == "splat_zones":
        payload["rule"] = "area"
    elif rule == "tower_control":
        payload["rule"] = "yagura"
    elif rule == "rainmaker":
        payload["rule"] = "hoko"

    ###########
    ## STAGE ##
    ###########
    stage = int(result["stage"]["id"])
    payload["stage"] = translate_stages[stage]

    ############
    ## WEAPON ##
    ############
    weapon = int(result["player_result"]["player"]["weapon"]["id"])
    payload["weapon"] = translate_weapons[weapon]

    ############
    ## RESULT ##
    ############
    team_result = result["my_team_result"]["key"] # victory, defeat
    if team_result == "victory":
        payload["result"] = "win"
    elif team_result == "defeat":
        payload["result"] = "lose"

    ##########################
    ## TEAM PERCENTS/COUNTS ##
    ##########################
    try:
        my_percent    = result["my_team_percentage"]
        their_percent = result["other_team_percentage"]
    except KeyError:
        pass # don't need to handle - won't be put into the payload unless relevant

    try:
        my_count    = result["my_team_count"]
        their_count = result["other_team_count"]
    except:
        pass

    mode = result["type"] # regular, gachi, league, fes
    if mode == "regular" or mode == "fes":
        payload["my_team_percent"] = my_percent
        payload["his_team_percent"] = their_percent
    elif mode == "gachi" or mode == "league":
        payload["my_team_count"] = my_count
        payload["his_team_count"] = their_count
        if my_count == 100 or their_count == 100:
            payload["knock_out"] = "yes"
        else:
            payload["knock_out"] = "no"

    ################
    ## TURF INKED ##
    ################
    turfinked = result["player_result"]["game_paint_point"] # without bonus
    if rule == "turf_war": # only upload if TW
        if team_result == "victory":
            payload["my_point"] = turfinked + 1000 # win bonus
        else:
            payload["my_point"] = turfinked

    #################
    ## KILLS, ETC. ##
    #################
    kill    = result["player_result"]["kill_count"]
    k_or_a  = result["player_result"]["kill_count"] + result["player_result"]["assist_count"]
    special = result["player_result"]["special_count"]
    death   = result["player_result"]["death_count"]
    payload["kill"]       = kill
    payload["kill_or_assist"] = k_or_a
    payload["special"]    = special
    payload["death"]      = death

    ###########
    ## LEVEL ##
    ###########
    level_before = result["player_result"]["player"]["player_rank"]
    level_after  = result["player_rank"]
    payload["level"]       = level_before
    payload["level_after"] = level_after

    ##########
    ## RANK ##
    ##########
    try: # only occur in either TW xor ranked
        rank_before = result["player_result"]["player"]["udemae"]["name"].lower()
        rank_after  = result["udemae"]["name"].lower()
        if rank_before == None:
            rank_before = "c-"
            rank_after = "c-"
    except: # in case of private battles where a player has never played ranked before
        rank_before = "c-"
        rank_after = "c-"
    if rule != "turf_war": # only upload if ranked
        payload["rank"]       = rank_before
        payload["rank_after"] = rank_after

    #####################
    ## START/END TIMES ##
    #####################
    try:
        elapsed_time = result["elapsed_time"] # apparently only a thing in ranked
    except KeyError:
        elapsed_time = 180 # turf war - 3 minutes in seconds
    payload["start_at"] = result["start_time"]
    payload["end_at"]   = result["start_time"] + elapsed_time

    ###################
    ## BATTLE NUMBER ##
    ###################
    bn = result["battle_number"]
    if not p_flag: # -p not provided
        payload["private_note"] = "Battle #" + bn

    ############################
    ## SPLATFEST TITLES/POWER ##
    ############################ https://github.com/fetus-hina/stat.ink/blob/master/API.md
    if mode == "fes":
        title_before = result["player_result"]["player"]["fes_grade"]["rank"]
        title_after = result["fes_grade"]["rank"]
        payload["fest_power"] = result["fes_power"]
        payload["my_team_power"] = result["my_estimate_fes_power"]
        payload["his_team_power"] = result["other_estimate_fes_power"]
        if title_before == 0:
            payload["fest_title"] = "fanboy"
        elif title_before == 1:
            payload["fest_title"] = "fiend"
        elif title_before == 2:
            payload["fest_title"] = "defender"
        elif title_before == 3:
            payload["fest_title"] = "champion"
        elif title_before == 4:
            payload["fest_title"] = "king"
        if title_after == 0:
            payload["fest_title_after"] = "fanboy"
        elif title_after == 1:
            payload["fest_title_after"] = "fiend"
        elif title_after == 2:
            payload["fest_title_after"] = "defender"
        elif title_after == 3:
            payload["fest_title_after"] = "champion"
        elif title_after == 4:
            payload["fest_title_after"] = "king"

    ################
    ## SCOREBOARD ##
    ################
    mystats = [mode, rule, team_result, k_or_a, death, special, weapon, level_before, rank_before, turfinked]
    payload = set_scoreboard(payload, result, mystats)

    ##########
    ## GEAR ## not in API v2 yet
    ########## https://github.com/fetus-hina/stat.ink/blob/master/API.md#gears
    # headgear_id = result["player_result"]["player"]["head"]["id"]
    # clothing_id = result["player_result"]["player"]["clothes"]["id"]
    # shoes_id    = result["player_result"]["player"]["shoes"]["id"]
    # payload["headgear"] = translate_headgear[int(headgear_id)]
    # payload["clothing"] = translate_clothing[int(clothing_id)]
    # payload["shoes"]    = translate_shoes[int(shoes_id)]

    ###############
    ## ABILITIES ## not in API v2 yet
    ############### https://github.com/fetus-hina/stat.ink/blob/master/doc/api-1/constant/ability.md
    # headgear_subs, clothing_subs, shoes_subs = ([-1,-1,-1] for i in xrange(3))
    # for j in xrange(3):
    #     try:
    #         headgear_subs[j] = result["player_result"]["player"]["head_skills"]["subs"][j]["id"]
    #     except:
    #         headgear_subs[j] = '-1'
    #     try:
    #         clothing_subs[j] = result["player_result"]["player"]["clothes_skills"]["subs"][j]["id"]
    #     except:
    #         clothing_subs[j] = '-1'
    #     try:
    #         shoes_subs[j] = result["player_result"]["player"]["shoes_skills"]["subs"][j]["id"]
    #     except:
    #         shoes_subs[j] = '-1'
    # payload["headgear_main"]   = translate_ability[int(headgear_main)]
    # payload["clothing_main"]   = translate_ability[int(clothing_main)]
    # payload["shoes_main_name"] = translate_ability[int(shoes_main)]
    # payload["headgear_sub1"] = translate_ability[int(headgear_subs[0])]
    # payload["headgear_sub2"] = translate_ability[int(headgear_subs[1])]
    # payload["headgear_sub3"] = translate_ability[int(headgear_subs[2])]
    # payload["clothing_sub1"] = translate_ability[int(clothing_subs[0])]
    # payload["clothing_sub2"] = translate_ability[int(clothing_subs[1])]
    # payload["clothing_sub3"] = translate_ability[int(clothing_subs[2])]
    # payload["shoes_sub1"]    = translate_ability[int(shoes_subs[0])]
    # payload["shoes_sub2"]    = translate_ability[int(shoes_subs[1])]
    # payload["shoes_sub3"]    = translate_ability[int(shoes_subs[2])]

    #############
    ## DRY RUN ##
    #############
    if t_flag: # -t provided
        payload["test"] = "dry_run" # works the same as 'validate' for now

    #**************
    #*** OUTPUT ***
    #**************
    if debug:
        print ""
        print json.dumps(payload).replace("\"", "'")
    else:
        # POST to stat.ink
        url     = 'https://stat.ink/api/v2/battle'
        auth    = {'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json'}

        if payload["agent"] != os.path.splitext(sys.argv[0])[0]:
            print "Could not upload. Please contact @frozenpandaman on Twitter/GitHub for assistance."
            exit(1)
        r2 = requests.post(url, headers=auth, json=payload)

        # Response
        try:
            print "Battle uploaded to " + r2.headers.get('location') # display url
        except TypeError: # r.headers.get is likely NoneType, i.e. we received an error
            if t_flag:
                print "Battle - message from server:"
            else:
                print "Error uploading battle. Message from server:"
            print r2.content
            if not t_flag:
                cont = raw_input('Continue (y/n)? ')
                if cont in ['n', 'N', 'no', 'No', 'NO']:
                    exit(1)

if __name__=="__main__":
    result, is_p, is_t, is_d = parse_arguments()
    post_battle(result, payload, is_p, is_t, is_d)
    if is_d:
        print ""
