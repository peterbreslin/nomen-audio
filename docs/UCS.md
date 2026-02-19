# UNIVERSAL CATEGORY SYSTEM FILENAMING CONVENTION

The UCS strongly encourages a special structure for filenames. If adhered to, this structure in the filename allows automated scripts in various programs to automatically parse out information from the filename into various fields of Metadata for the end user.

It also encourages supplying a basic amount of information in the filename itself. Information that can answer the following questions:

> _What category and subcategory does this sound belong to?_
> _What is the sound?_
> _Who made the sound?_
> _What project or library was it made for?_

The basic UCS filename structure requires at least four blocks of information, and each block must be separated by an `_`. The `_` may only be used to define these blocks, and shouldn’t be used elsewhere.

The four basic blocks of the filename as defined and structured as follows:

`CatID_FXName_CreatorID_SourceID`

- **CatID** = Abbreviated **Category** / **Subcategory** (as defined by UCS list)
- **FXName** = Brief Description or Title (under 25 characters preferably)
- **CreatorID** = Sound Designer, Recordist or Vendor (or abbreviation for them)
- **SourceID** = Project, Show or Library name (or abbreviation representing it)

The **CatID** represents both the **Category** and **SubCategory** in abbreviated form as defined in Universal Category System list.

The **CatID** is really at the heart of this entire system. It is the **only requirement** to use the system, and it must not be altered from the list. We ask that the case also be honored. It is what guarantees that anyone releasing a wood door agrees that the short abbreviated form for this **Category** / **SubCategory** pair will be DOORWood.

This will allow any user of the system to know exactly where that sound belongs. And using many of the scripts developed and being developed, most common database programs can parse that out easily into the **Category** and **SubCategory** fields, and also in some cases build a CategoryFull field by looking up the **CatID**, matching to the list, and then pasting the matched fields together with a hyphen. So DOORWood becomes DOORS-WOOD

An example of a section of the USC list is below:

| Category | SubCategory      | CatID     | CatShort |
| :------- | :--------------- | :-------- | :------- |
| AIR      | MISC             | AIRMisc   | AIR      |
| AIR      | BLOW             | AIRBlow   | AIR      |
| AIR      | BURST            | AIRBrst   | AIR      |
| AIR      | HISS             | AIRHiss   | AIR      |
| AIR      | SUCTION          | AIRSuck   | AIR      |
| AIRCRAFT | MISC             | AEROMisc  | AERO     |
| AIRCRAFT | HELICOPTER       | AEROHeli  | AERO     |
| AIRCRAFT | JET              | AEROJet   | AERO     |
| AIRCRAFT | MECHANISM        | AEROMech  | AERO     |
| AIRCRAFT | MILITARY         | AEROMil   | AERO     |
| AIRCRAFT | PROP             | AEROProp  | AERO     |
| AIRCRAFT | RADIO CONTROLLED | AERORadio | AERO     |
| AIRCRAFT | ROCKET           | AERORckt  | AERO     |

**CatShort** is the abbreviation only for the Category. At the moment it’s not utilized as a metadata field, but is offered on the list for future use, or user use. It is NOT used as part of the filename, the full **CatID** must be used at the head of the file.

**FXName** is the next block of data in a UCS filename. Think of it as a Title. The goal is to give a brief description of the sound; around 25 characters is usually ideal for the length of this field. This is not meant to replace a more elaborate ‘Description’ metadata field, but is meant so that at a glance, the user will understand what the sound file is without having to listen to it.

**CreatorID** shows you who recorded or designed the sound. A vendor would place their name here… or you would put your name or initials. Most likely you’ll probably want to put an abbreviation here. This is entirely up to each vendor or creator. UCS has a vendor list that allows a vendor to assign an official abbreviation to be used in filenames. There will be more documentation about defining this information in the Vendors folder.

At first glance, a user should be able to clearly tell that the sound came from you, without having to even need access to the metadata. You could put your entire name here, or the full name of your company. We only ask that you keep this consistent on all of your products. And again if your name is long, consider an abbreviate form if that makes sense to you.

**SourceID** holds the name or abbreviated version of the show, project or in this case library.

Again as vendors and creatures it’s up to you how to best utilize this block of text, but it should contain somehow the name of your library that this sound belongs to, or the show it was designed or recorded for Again we’d encourage some sort of abbreviation if your library name is very long.

---

## OPTIONAL BLOCKS

There are three optional blocks of information also available in the filename to satisfy specific instances. They are defined as a **UserCategory**, **VendorCategory**, and **UserData**.

A breakdown of all blocks in a UCS full filename is as follows:

`CatID(-UserCategory)_(VendorCategory-)FXName_CreatorID_SourceID_UserData`

- **UserCategory** = An optional tail extension of the **CatID** block that can be used as a user defined category, microphone, perspective etc.
- **VendorCategory** = An option head extension to the **FXName** block usable by vendors to define a library specific category. For example, the specific name of a gun, vehicle, location, etc.
- **UserData** = A User defined space, often used for an ID or Number for guaranteeing that the Filename is 100% unique… or storing things such as microphone type, location, perspective etc. This space is not currently mapped to user metadata but each user may choose to map this chunk of data to a database field depending on how they use it…

**UserCategory** is an optional tail extension to the CatID. It is designated by simply placing a – after the CatID and adding a user defined term or abbreviation. Vendors should avoid using this area of the filename.

It is designed to allow users to create their own sort of sub-sub-category, a third category of their choosing. The user might also choose to define this as a set of abbreviations and a look up table. A common use might be INT and EXT for INTERIOR and EXTERIOR.

**VendorCategory** is an optional head extension to the FXName block. It is defined as the first block of text immediately after the first `_`, and up to the very next –. It is meant as an optional library specific category definable by a vendor to organize a library internally. As many libraries already have some logical category system in place, this block is meant as a way to preserve that information for vendors when adapting a library to the UCS standard.

**UserData** is the last chunk of data in our filename structure, and it’s completely freeform. Each user or vendor will decide how to use this information, as we do not assign it to any standard metadata field. You could store here a microphone or perspective, a unique filename number, or any other information you want to distribute to the end user.

Additional `_`s used in this block, while discouraged, are not prohibited.

---

Let’s look at some filename examples:

`GUNAuto_Uzi 9mm Rapid Fire Close Up Short Bursts_TN_DORY`

Is a valid filename because it contains all four required parts separated by `_`s

**CatID** is defined as GUNAuto, and therefore **Category** is defined as **GUNS** and the **SubCategory** as **AUTOMATIC**. **CategoryFull** is defined as **GUNS-AUTOMATIC** just by use of the simple **CatID** at the head of the filename.

**FXName** is defined as “Uzi 9mm Rapid Fire Close Up Short Bursts”.

**CreatorID** is designated “TN”, and via a lookup table, this information can be easily parsed out to “Tim Nielsen”.

**SourceID** is designated as the “DORY”, and again, via a simple lookup table, this information could be parsed out into “Finding Dory”, the name of the project.

Notice how we are using abbreviations in the **CatID**, **CreatorID** and **SourceID** blocks in an attempt to keep the filename length manageable, but still readable.

`GUNAuto_UZI 9mm Rapid Fire Close Up Short Bursts_TN_DORY_WideStereoMKH8020`

In this example, the filename adds the information ‘WideStereoMKH8020’ into the **UserData** block of the file. By default this won’t be assigned to a particular metadata field, but a user could easily script this to be placed in a metadata field of their choosing. Again this **UserData** block can be used to hold any additional information the creator deems important.

`GUNAuto-INT_UZI 9mm Rapid Fire Close Up Short Bursts_TN_DORY`

In this filename, the optional **UserCategory** of ‘INT’ has been defined by the adding the **-INT** directly after the **CatID**. Tools in database programs could potentially take this term, and place into a metadata field called **UserCategory**. This field could be defined for things like mic perspectives, or perhaps a show specific category for a project the user routinely uses. It could optionally be defined as an abbreviation and a lookup table as well.

`GUNAuto_UZI 9mm-Rapid Fire Close Up Short Bursts_TN_DORY`

In this filename, no **UserCategory** is defined, but by adding the text **UZI 9mm-** to the head of the **FXName** block, the **VendorCategory** has been defined as “UZI 9mm”.

While the entire block of data between the first and second `_` is technically the FX Name. (UZI 9mm-Rapid Fire Close Up Short Bursts), the piece of information between that first `_` and the first – is also now defined as a **VendorCategory**. Programs could easily to scripted to break out this piece of information and place in the **VendorCategory** metadata field.

One final example shows a full UCS filename, with all blocks filled:

`GUNAuto-EXT_UZI 9mm-Rapid Fire Close Up Short Bursts_TN_NONE_416-MKH8040-DualMono`

This filename demonstrates the use of all assigned blocks in a UCS filename. In this case we have defined, simply by the placement of `_`s and –s in the filename, the following information:

- **CatID** = GUNAuto (GUNS-AUTOMATIC)
- **UserCategory** = EXT (in this case to designate by the user this is an EXTERIOR recording)
- **FXName** = UZI 9mm-Rapid Fire Close Up Short Bursts
- **VendorCategory** = UZI 9mm
- **CreatorID** = TN (which is a user defined abbreviation for Tim Nielsen)
- **SourceID** = NONE (which would indicate that this was not recorded for a particular project)
- **UserData** = 416-MKH8040-DualMono

### CONCLUSION

Just to reiterate, the **only requirement** of the UCS system is the designation of every file to one of the **Category** / **SubCategory** pairs in the list, and the associate **CatID**\_ being placed at the head of the filename. The rest of the filename structure is completely optional.

The immediate benefit of adhering to this ‘requirement’ is that the purchaser of your library will instantly know that the sound in question belongs to the **Category** / **SubCategory** pair GUNS-AUTOMATIC because GUNAuto is defined as that in the list.

This rigid placement of GUNAuto\_ at the head of the filename will also allow various scripts and parsing of that information back into metadata fields for the user.

Also by placing the **CatID** at the beginning of the filename, all GUNS-AUTOMATIC will now sort together in any list, or region list in any DAW, on the folder level, etc.
