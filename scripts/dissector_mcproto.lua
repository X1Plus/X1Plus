local mcproto = Proto("mcproto", "Bambu MC wire protocol")
local mccommands = DissectorTable.new("mcproto.command", "Bambu MC protocol commands", ftypes.UINT16, base.HEX, mcproto)

local devices = {
	[3] = "MC",
	[6] = "AP",
	[7] = "AMS",
	[8] = "TH",
	[9] = "AP2",
	[0xE] = "AHB",
	[0xF] = "EXT",
	[0x13] = "CTC",
}

local fields = {
	capture_source = ProtoField.uint8("mcproto.capture_source", "Capture source", nil,
		{ [1] = "Serial port write from forward", [2] = "Serial port read from forward" }),
	flags = ProtoField.uint8("mcproto.flags", "Flags", base.HEX),
	flags_wants_response = ProtoField.bool("mcproto.flags.wants_response", "RPC wants response", ftypes.UINT8, nil, 0x01),
	flags_is_initiator = ProtoField.bool("mcproto.flags.is_initiator", "Message is initiator", ftypes.UINT8, nil, 0x04),
	request = ProtoField.framenum('mcproto.request', 'Request', base.NONE, frametype.REQUEST),
	response = ProtoField.framenum('mcproto.response', 'Response', base.NONE, frametype.RESPONSE),
	seq = ProtoField.uint16("mcproto.seq", "Sequence number", base.DEC),
	dest = ProtoField.uint16("mcproto.dest", "Destination", nil, devices),
	src = ProtoField.uint16("mcproto.src", "Source", nil, devices),
	command = ProtoField.uint16("mcproto.command", "Command", base.HEX),
	payload = ProtoField.none("mcproto.payload", "Payload"),
}

mcproto.fields = { }

local reqmap = {}
local respmap = {}

for _,v in pairs(fields) do table.insert(mcproto.fields,v) end

local f_src = Field.new("mcproto.src")
local f_dest = Field.new("mcproto.dest")
local f_seq = Field.new("mcproto.seq")
local f_wants_response = Field.new("mcproto.flags.wants_response")
local f_is_initiator = Field.new("mcproto.flags.is_initiator")
local f_command = Field.new("mcproto.command")

function mcproto.dissector(buf, pinfo, root)
	pinfo.cols.protocol:set("MCPROTO")
	local length = buf:len()
	if length == 0 then return 0 end
	
	local tree = root:add(mcproto, buf:range(1,len), "Bambu bus protocol data")
	tree:add(fields.capture_source, buf:range(0, 1))
	local flag_tree = tree:add(fields.flags, buf:range(2, 1))
		flag_tree:add(fields.flags_wants_response, buf:range(2, 1))
		flag_tree:add(fields.flags_is_initiator, buf:range(2, 1))

	tree:add_le(fields.seq, buf:range(3, 2))
	local seq = f_seq()()
	local is_initiator = f_is_initiator()()
	
	if not pinfo.visited then
		if is_initiator then
			reqmap[seq] = reqmap[seq] or {}
			table.insert(reqmap[seq], pinfo.number)
		else
			respmap[seq] = respmap[seq] or {}
			table.insert(respmap[seq], pinfo.number)
		end
	end
	
	if is_initiator and respmap[seq] then
		for _,pnum2 in ipairs(respmap[seq]) do
			if pnum2 > pinfo.number then
				tree:add(fields.response, pnum2)
				break
			end
		end
	end
	if (not is_initiator) and reqmap[seq] then
		local last_pnum2 = nil
		for _,pnum2 in ipairs(reqmap[seq]) do
			if pnum2 < pinfo.number then
				last_pnum2 = pnum2
			end
		end
		if last_pnum2 then tree:add(fields.request, last_pnum2) end
	end
	-- look at packet length, and add an expert to complain if needed
	-- look at CRC, and add an expert to complain if needed
	
	pinfo.cols.info:set("[" .. (is_initiator and (f_wants_response()() and "REQ " or "") or "RSP ") .. "#" .. seq .. "] ")
	
	tree:add(fields.dest, buf:range(8, 2))
	tree:add(fields.src, buf:range(10, 2))
	
	pinfo.cols.src:set(devices[f_src()()] or f_src()())
	pinfo.cols.dst:set(devices[f_dest()()] or f_dest()())

	tree:add_le(fields.command, buf:range(12, 2)) -- really, { command_set, command_id }, but this is much easier
	
	local payload = buf:range(14, length - 16)
	mccommands:try(f_command()(), payload:tvb(), pinfo, tree)
end

-- Now for some commands!
function mk_cmd(cmdset, cmdid, name, fields, dis)
	local myname = "mcproto." .. name
	local proto = Proto(myname, name)
	proto.fields = {}
	for _,v in pairs(fields) do table.insert(proto.fields,v) end
	proto.dissector = function (buf, pinfo, root) return dis(proto, fields, buf, pinfo, root) end
	mccommands:set(cmdset * 256 + cmdid, proto)
	return proto
end

function mk_cmd_opaque(cmdset, cmdid, name)
	local myname = "mcproto." .. name
	mk_cmd(cmdset, cmdid, name,
		{ payload = ProtoField.bytes(myname..".payload", "Payload") },
		function (proto, fields, buf, pinfo, root)
			local len = buf:len()
			local tree = root:add(proto, buf:range(0, len), name)
			tree:add(fields.payload, buf:range(0, len))
			pinfo.cols.info:append(name)
		end)
end

mk_cmd_opaque(1, 1, "ping")
mk_cmd_opaque(1, 3, "get_version")
mk_cmd_opaque(1, 4, "sync_timestamp")
mk_cmd_opaque(1, 6, "mcu_upgrade")
mk_cmd_opaque(1, 8, "mcu_hms")
mk_cmd_opaque(1, 9, "factory_reset")
mk_cmd_opaque(2, 5, "gcode_execute_state")
mk_cmd_opaque(2, 6, "gcode_request")
mk_cmd_opaque(2, 8, "publish_dds_cmn_recorder")
mk_cmd(2, 9, "mcu_display_message",
	{ message = ProtoField.string("mcproto.mcu_display_message.message", "Message") },
	function (proto, fields, buf, pinfo, root)
		local len = buf:len()
		local tree = root:add(proto, buf:range(0, len), "mcu_display_message")
		tree:add(fields.message, buf:range(0, len))
		pinfo.cols.info:append("mcu_display_message: \""..buf:range(0, len):string().."\"")
	end
)
	
mk_cmd_opaque(2, 10, "vosync")
mk_cmd_opaque(2, 0xb, "gcode_ctx")
mk_cmd_opaque(2, 0xc, "mc_state")
mk_cmd(2, 0xf, "link_ams_report",
	{
		ams_exist = ProtoField.uint8("mcproto.link_ams_report.ams_exist", "ams_exist"),
		tray_exist = ProtoField.uint16("mcproto.link_ams_report.tray_exist", "tray_exist"),
		tray_read_done = ProtoField.uint16("mcproto.link_ams_report.tray_read_done", "tray_read_done"),
		tray_reading = ProtoField.uint16("mcproto.link_ams_report.tray_reading", "tray_reading"),
		tray_is_bbl = ProtoField.uint16("mcproto.link_ams_report.tray_is_bbl", "tray_is_bbl"),
		insert_poweron_remain = ProtoField.uint8("mcproto.link_ams_report.insert_poweron_remain", "insert_poweron_remain"),
	},
	function (proto, fields, buf, pinfo, root)
		local tree = root:add(proto, buf:range(0, 0x1d), "link_ams_report")
		tree:add(fields.ams_exist, buf:range(0, 1))
		tree:add_le(fields.tray_exist, buf:range(1, 4))
		tree:add_le(fields.tray_read_done, buf:range(5, 2))
		tree:add_le(fields.tray_reading, buf:range(7, 2))
		tree:add_le(fields.tray_is_bbl, buf:range(9, 2))
		tree:add_le(fields.insert_poweron_remain, buf:range(11, 2))
		
		pinfo.cols.info:append("link_ams_report: ams_exist "..f_ams_exist()())
	end
)
f_ams_exist = Field.new("mcproto.link_ams_report.ams_exist")

mk_cmd_opaque(2, 0x11, "ack_tray_info")
mk_cmd_opaque(2, 0x16, "gcode_line_handle")
mk_cmd_opaque(2, 0x17, "ams_mapping")
mk_cmd_opaque(2, 0x18, "ams_tray_info_write_ack")
mk_cmd_opaque(2, 0x19, "ams_user_settings")
mk_cmd_opaque(2, 0x1b, "hw_info_voltage")
mk_cmd_opaque(2, 0x1c, "link_ams_tray_consumption_ack")
mk_cmd_opaque(2, 0x1d, "pack_get_part_info_ack")
mk_cmd_opaque(2, 0x22, "extrusion_result_update")
mk_cmd_opaque(2, 0x24, "fila_ams_get")
mk_cmd_opaque(2, 0x25, "mc_get_skipped_obj_list")

-- NEW FORWARD
local amsv2_pl_types = {
	[0] = "AMS desc",
	[1] = "Tray desc",
	[2] = "AMS flags",
	[3] = "Extruder info",
}
mk_cmd(2, 0x1f, "ams_v2_ams_info_update",
	{
		subinfo_type = ProtoField.uint8("mcproto.ams_v2_ams_info_update.subinfo_type", "AMS subinfo type", nil, amsv2_pl_types),
		subinfo_length = ProtoField.uint8("mcproto.ams_v2_ams_info_update.subinfo_length", "AMS subinfo length"),
		insert_poweron_remain = ProtoField.uint8("mcproto.ams_v2_ams_info_update.insert_poweron_remain", "Insert / Poweron / Remain"),
		ams_id = ProtoField.uint8("mcproto.ams_v2_ams_info_update.ams_id", "AMS ID"),
		slot_id = ProtoField.uint8("mcproto.ams_v2_ams_info_update.slot_id", "Slot ID"),
		tray_status = ProtoField.uint8("mcproto.ams_v2_ams_info_update.tray_status", "Tray status"),
		ams_desc = ProtoField.none("mcproto.ams_v2_ams_info_update.ams_desc", "AMS descriptor"),
	},
	function (proto, fields, buf, pinfo, root)
		local length = buf:len()
		local ofs = 0
		local tree = root:add(proto, buf:range(0, length), "ams_v2_ams_info_update")
		
		local n_ams = 0
		local n_tray = 0
		
		while ofs < length do
			local pllen = buf:range(ofs+1, 1):uint() + 2
			local subbuf = buf:range(ofs, pllen):tvb()
			ofs = ofs + pllen
			local pltype = subbuf:range(0, 1):uint()
			local subtree = tree:add(proto, subbuf:range(0, pllen), "Subpayload")
			
			subtree:add(fields.subinfo_type, subbuf:range(0, 1))
			subtree:add(fields.subinfo_length, subbuf:range(1, 1))
			
			if pltype == 0 then -- AMS desc
				subtree:add(fields.ams_id, subbuf:range(2, 1))
				subtree:add(fields.ams_desc, subbuf:range(3, 9))
				n_ams = n_ams + 1
			elseif pltype == 1 then -- tray desc
				subtree:add(fields.ams_id, subbuf:range(2, 1))
				subtree:add(fields.slot_id, subbuf:range(3, 1))
				subtree:add(fields.tray_status, subbuf:range(4, 1))
				n_tray = n_tray + 1
			elseif pltype == 2 then -- AMS flags
				subtree:add(fields.insert_poweron_remain, subbuf:range(2, 1))
			elseif pltype == 3 then -- extruder info
			end
		end
		
		pinfo.cols.info:append("ams_v2_ams_info_update: ".. n_ams.." AMSes, "..n_tray.." trays")
	end
)

mk_cmd_opaque(2, 0x20, "ams_v2_mc_ams_mapping")
mk_cmd_opaque(2, 0x23, "link_ams_tray_consumption_ack2")
mk_cmd_opaque(2, 0x27, "part_info_ack_v2")
mk_cmd_opaque(2, 0x2c, "ams_filament_drying")
mk_cmd_opaque(2, 0x36, "mc_get_filament_info")
mk_cmd_opaque(2, 0x33, "mc_need_change_blade")
mk_cmd_opaque(2, 0x34, "mc_done_change_blade")
mk_cmd_opaque(2, 0x35, "mc_wait_unlock_laser")
mk_cmd_opaque(2, 0x39, "mc_button_press")
mk_cmd_opaque(2, 0x3a, "mc_set_ams_extruder_bind")
mk_cmd_opaque(2, 0x3b, "mc_ams_flush_param")
mk_cmd_opaque(2, 0x40, "mc_hotend_info")
mk_cmd_opaque(2, 0x41, "mc_hotend_sn_map")
mk_cmd_opaque(2, 0x46, "mc_get_plate_heigh")
mk_cmd_opaque(2, 0x47, "ams_v2_set_ams_led_ack")
mk_cmd_opaque(2, 0x48, "mc_motion_precision_result")
mk_cmd_opaque(2, 0x49, "mc_request_ext_tool_type")


mk_cmd_opaque(3, 1, "M971")
mk_cmd_opaque(3, 2, "M972")
mk_cmd_opaque(3, 5, "M963")
mk_cmd_opaque(3, 7, "M969")
mk_cmd_opaque(3, 6, "M965_b")
mk_cmd_opaque(3, 9, "M967")
mk_cmd_opaque(3, 11, "M973")
mk_cmd_opaque(3, 14, "M965")
mk_cmd_opaque(3, 49, "MC_M976")

mk_cmd_opaque(3, 50, "M977")
mk_cmd_opaque(3, 51, "M978")
mk_cmd_opaque(3, 52, "M981")
mk_cmd_opaque(3, 53, "M991")
mk_cmd_opaque(3, 81, "M987")
mk_cmd_opaque(3, 82, "SENSORCHECK")

mk_cmd_opaque(4, 1, "set_module_sn")
mk_cmd_opaque(4, 2, "get_module_sn")
mk_cmd_opaque(4, 3, "inject_module_key")
mk_cmd_opaque(4, 4, "get_inject_status")
mk_cmd_opaque(4, 5, "mcu_reboot")
mk_cmd_opaque(4, 6, "send_to_amt_core")
mk_cmd_opaque(4, 7, "set_module_lifecycle")
mk_cmd_opaque(4, 8, "get_module_lifecycle")
mk_cmd_opaque(4, 10, "inject_productcode")
mk_cmd_opaque(4, 11, "get_productcode")
